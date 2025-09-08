# route_pois_map_fn.py

import os
import math
import requests
import folium
from typing import Any, Tuple, List, Dict, Optional
from folium.plugins import (
    MarkerCluster, MiniMap, Fullscreen, MeasureControl,
    PolyLineTextPath, BeautifyIcon
)

from folium.features import DivIcon
from branca.element import Template, MacroElement
from urllib.parse import urlencode

API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
OUTPUT_HTML_DEFAULT = "route_pois_map.html"

ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
PLACES_URL = "https://places.googleapis.com/v1/places:searchNearby"
GEOLOCATION_URL = "https://maps.googleapis.com/maps/api/geocode/json"


# Marker styles by type
ICON_MAP: Dict[str, Dict[str, Any]] = {
    "electric_vehicle_charging_station": dict(color="purple", icon="bolt", prefix="fa"),
    "charging_station": dict(color="purple", icon="bolt", prefix="fa"),
    "gas_station": dict(color="green", icon="tint", prefix="fa"),
    "restaurant": dict(color="red", icon="cutlery", prefix="fa"),
    "tourist_attraction": dict(color="blue", icon="info-sign"),
}


def _annotate_distances_on_map(m, poi_list, total_route_km):
    # Unified style for POIs and total badge
    label_style = (
        "display:inline-block;"
        "background:rgba(0,0,0,0.72);"
        "color:#fff;"
        "padding:3px 6px;"
        "border-radius:6px;"
        "font-size:11px;"
        "white-space:nowrap;"
        "box-shadow:0 2px 6px rgba(0,0,0,0.25);"
    )

    # POI labels (auto-sized, no clipping)
    for i, p in enumerate(poi_list, 1):
        lat, lng = p["lat"], p["lng"]
        gap_km = p["gap_km"]
        label_html = f"<div style='{label_style}'>{i}. {gap_km:.1f} km</div>"
        folium.Marker(
            [lat, lng],
            icon=DivIcon(
                icon_size=None,          # allow autosize
                icon_anchor=(0, 0),
                class_name="",           # remove leaflet-div-icon defaults
                html=label_html,
            ),
            tooltip=f"{p['name']} • {p['type']} • gap {gap_km:.1f} km"
        ).add_to(m)

    # Center-top total distance badge (unchanged, but included for completeness)
    total_km_str = f"{total_route_km:.1f}"
    total_html = (
        "{% macro html(this, kwargs) %}"
        "<div style=\"position:fixed;top:12px;left:50%;transform:translateX(-50%);"
        "z-index:9999;padding:10px 14px;background:rgba(0,0,0,0.72);color:#fff;"
        "font-weight:600;border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,0.25);\">"
        "Total distance: " + total_km_str + " km"
        "</div>"
        "{% endmacro %}"
    )
    macro = MacroElement()
    macro._template = Template(total_html)
    m.get_root().add_child(macro)



def _cumulative_route_distances_m(path: List[Tuple[float,float]]) -> List[float]:
    if not path:
        return []
    c = [0.0]
    for i in range(1, len(path)):
        c.append(c[-1] + haversine_km(path[i-1], path[i]) * 1000.0)
    return c

def _project_point_along_route_m(
    p: Tuple[float,float], path: List[Tuple[float,float]], cum: List[float]
) -> Tuple[float, float]:
    if not path:
        return float("nan"), float("inf")
    if len(path) == 1:
        return 0.0, _min_distance_to_polyline_m(p, path)

    best_along = 0.0
    best_off = float("inf")
    for i in range(len(path) - 1):
        a, b = path[i], path[i+1]
        lat0 = (a[0] + b[0] + p[0]) / 3.0
        my, mx = _meters_per_deg(lat0)
        ax, ay = a[1]*mx, a[0]*my
        bx, by = b[1]*mx, b[0]*my
        px, py = p[1]*mx, p[0]*my
        bax, bay = ax - bx, ay - by
        bpx, bpy = px - bx, py - by
        seg_len2 = bax*bax + bay*bay
        if seg_len2 == 0:
            off = math.hypot(px - bx, py - by)
            along = cum[i]
        else:
            t = max(0.0, min(1.0, (bpx*bax + bpy*bay) / seg_len2))
            cx, cy = bx + t*bax, by + t*bay
            off = math.hypot(px - cx, py - cy)
            along = cum[i] + t * math.sqrt(seg_len2)
        if off < best_off:
            best_off = off
            best_along = along
    return best_along, best_off

def _primary_type_for_place(p: dict, requested_types: List[str]) -> str:
    types = p.get("types") or []
    for t in requested_types:
        if t in types:
            return t
    return types[0] if types else "point_of_interest"


# --------------------------- Core utils ---------------------------
def summarize_poi_distances_along_route(
    path: List[Tuple[float,float]],
    recos: Dict[str, List[dict]],
    requested_recos: Dict[str,int]
):
    """
    Returns:
      total_route_km: float
      annotated_sorted: list of dicts in encounter order, each:
        {
          "name": str,
          "type": str,
          "lat": float, "lng": float,
          "along_m": float,
          "gap_km": float   # from previous POI (or from start for first)
        }
    """
    cum = _cumulative_route_distances_m(path)
    total_route_km = (cum[-1] / 1000.0) if cum else 0.0
    requested_types_list = list(requested_recos.keys())

    ann = []
    for typ, picks in recos.items():
        for p in picks:
            if not p or not p.get("location"):
                continue
            loc = p["location"]
            lat, lng = loc.get("latitude"), loc.get("longitude")
            if lat is None or lng is None:
                continue
            along_m, _ = _project_point_along_route_m((lat, lng), path, cum)
            name = (p.get("displayName") or {}).get("text", "Place")
            ann.append({
                "name": name,
                "type": _primary_type_for_place(p, requested_types_list),
                "lat": float(lat), "lng": float(lng),
                "along_m": float(along_m),
            })

    ann.sort(key=lambda x: x["along_m"])

    prev_along = 0.0
    for item in ann:
        item["gap_km"] = max(0.0, (item["along_m"] - prev_along) / 1000.0)
        prev_along = item["along_m"]

    return total_route_km, ann


def get_location_coordinates(address: str) -> Tuple[float, float]:
    if not API_KEY:
        raise RuntimeError("Set GOOGLE_MAPS_API_KEY environment variable.")
    r = requests.get(GEOLOCATION_URL, params={"address": address, "key": API_KEY}, timeout=30)
    r.raise_for_status()
    data = r.json()
    if data.get("status") != "OK":
        raise RuntimeError(f"Geocoding failed: {data.get('status')}")
    loc = data["results"][0]["geometry"]["location"]
    return loc["lat"], loc["lng"]

def decode_polyline(encoded: str) -> List[Tuple[float, float]]:
    idx = 0; lat = 0; lng = 0; out: List[Tuple[float,float]] = []
    while idx < len(encoded):
        shift = 0; result = 0
        while True:
            b = ord(encoded[idx]) - 63; idx += 1
            result |= (b & 0x1f) << shift; shift += 5
            if b < 0x20: break
        dlat = ~(result >> 1) if (result & 1) else (result >> 1); lat += dlat

        shift = 0; result = 0
        while True:
            b = ord(encoded[idx]) - 63; idx += 1
            result |= (b & 0x1f) << shift; shift += 5
            if b < 0x20: break
        dlng = ~(result >> 1) if (result & 1) else (result >> 1); lng += dlng

        out.append((lat/1e5, lng/1e5))
    return out

def compute_route(origin: str, destination: str, vehicle_emission_type: str) -> List[Tuple[float,float]]:
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": "routes.polyline.encodedPolyline,routes.legs.polyline.encodedPolyline",
    }
    o_lat, o_lng = get_location_coordinates(origin)
    d_lat, d_lng = get_location_coordinates(destination)
    payload = {
        "origin": {"location": {"latLng": {"latitude": o_lat, "longitude": o_lng}}},
        "destination": {"location": {"latLng": {"latitude": d_lat, "longitude": d_lng}}},
        "routeModifiers": {"vehicleInfo": {"emissionType": vehicle_emission_type}},
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE_OPTIMAL",
        "polylineQuality": "HIGH_QUALITY",
        "polylineEncoding": "ENCODED_POLYLINE",
        "requestedReferenceRoutes": ["FUEL_EFFICIENT"]
    }
    r = requests.post(ROUTES_URL, headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    routes = r.json().get("routes", [])
    if not routes:
        raise RuntimeError("No route returned")
    enc = routes[0].get("polyline", {}).get("encodedPolyline")
    if not enc:
        # fallback to legs
        coords: List[Tuple[float,float]] = []
        for leg in routes[0].get("legs", []):
            leg_enc = leg.get("polyline", {}).get("encodedPolyline")
            if leg_enc:
                coords += decode_polyline(leg_enc)
        if not coords:
            raise RuntimeError("No polyline found in route response")
        return coords
    return decode_polyline(enc)

def split_path(path: List[Tuple[float,float]], n: int) -> List[List[Tuple[float,float]]]:
    if n <= 0:
        return []
    L = len(path)
    if L == 0:
        return [[] for _ in range(n)]
    cuts = [round(i * L / n) for i in range(n+1)]
    chunks = [path[cuts[i]:cuts[i+1]] for i in range(n)]
    for i in range(n):
        if not chunks[i]:
            idx = min(round((i + 0.5) * L / n), L-1)
            chunks[i] = [path[idx]]
    return chunks

def midpoint_of_chunk(chunk: List[Tuple[float,float]]) -> Tuple[float,float]:
    return chunk[len(chunk)//2] if chunk else (0.0, 0.0)

def haversine_km(a: Tuple[float,float], b: Tuple[float,float]) -> float:
    R = 6371.0
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat, dlon = lat2-lat1, lon2-lon1
    h = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 2*R*math.asin(math.sqrt(h))

def _meters_per_deg(lat_deg: float) -> Tuple[float, float]:
    lat = math.radians(lat_deg)
    m_per_deg_lat = 111132.92 - 559.82*math.cos(2*lat) + 1.175*math.cos(4*lat)
    m_per_deg_lon = 111412.84*math.cos(lat) - 93.5*math.cos(3*lat)
    return m_per_deg_lat, m_per_deg_lon

def _point_segment_distance_m(p: Tuple[float,float], a: Tuple[float,float], b: Tuple[float,float]) -> float:
    lat0 = (a[0] + b[0] + p[0]) / 3.0
    my, mx = _meters_per_deg(lat0)
    px, py = (p[1]*mx, p[0]*my)
    ax, ay = (a[1]*mx, a[0]*my)
    bx, by = (b[1]*mx, b[0]*my)
    bax, bay = (ax - bx, ay - by)
    bpx, bpy = (px - bx, py - by)
    seg_len2 = bax*bax + bay*bay
    if seg_len2 == 0:
        return math.hypot(px - bx, py - by)
    t = max(0.0, min(1.0, (bpx*bax + bpy*bay) / seg_len2))
    cx, cy = (bx + t*bax, by + t*bay)
    return math.hypot(px - cx, py - cy)

def _min_distance_to_polyline_m(p: Tuple[float,float], poly: List[Tuple[float,float]]) -> float:
    if not poly:
        return float("inf")
    if len(poly) == 1:
        lat0 = (p[0] + poly[0][0]) / 2
        my, mx = _meters_per_deg(lat0)
        dx = (p[1] - poly[0][1]) * mx
        dy = (p[0] - poly[0][0]) * my
        return math.hypot(dx, dy)
    mind = float("inf")
    for i in range(len(poly)-1):
        d = _point_segment_distance_m(p, poly[i], poly[i+1])
        if d < mind:
            mind = d
    return mind

# --------------------------- Places & ranking ---------------------------

def places_nearby(lat: float, lng: float, search_radius_m: float, result_count: int,
                  included_types: Optional[List[str]] = None) -> List[dict]:
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": (
            "places.id,places.displayName,places.formattedAddress,places.location,"
            "places.regularOpeningHours.weekdayDescriptions,"
            "places.currentOpeningHours.openNow,"
            "places.types,"
            "places.rating,places.userRatingCount,places.priceLevel,"
            "places.googleMapsUri"
        )
    }
    payload: Dict[str, Any] = {
        "locationRestriction": {
            "circle": {"center": {"latitude": lat, "longitude": lng}, "radius": float(search_radius_m)}
        },
        "maxResultCount": int(result_count)
    }
    if included_types:
        payload["includedTypes"] = included_types
    r = requests.post(PLACES_URL, headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    return r.json().get("places", []) or []

def pick_best_place(candidates: List[dict], center: Tuple[float,float],
                    prefer_open_now: bool = True,
                    min_user_ratings: int = 50) -> Optional[dict]:
    if prefer_open_now:
        open_now = [p for p in candidates if (p.get("currentOpeningHours") or {}).get("openNow")]
        if open_now:
            candidates = open_now
    candidates = [p for p in candidates if (p.get("userRatingCount") or 0) >= min_user_ratings]
    if not candidates:
        return None
    def key(p):
        rcnt = p.get("userRatingCount") or 0
        rating = p.get("rating") or 0.0
        loc = p.get("location") or {}
        dist_km = haversine_km(center, (loc.get("latitude",0), loc.get("longitude",0)))
        return (rcnt, rating, -dist_km)  # primary: reviews; secondary: stars; tertiary: proximity
    return sorted(candidates, key=key, reverse=True)[0]

def _sample_points(poly: List[Tuple[float,float]], k: int) -> List[Tuple[float,float]]:
    if not poly:
        return []
    if k <= 1:
        return [midpoint_of_chunk(poly)]
    idxs = [round((i+1) * (len(poly)-1) / (k+1)) for i in range(k)]
    return [poly[i] for i in idxs]

# --------------------------- Selection per type ---------------------------

def _icon_for_place(p: dict, fallback: str = "point_of_interest") -> folium.Icon:
    types = set(p.get("types") or [])
    for t, args in ICON_MAP.items():
        if t in types:
            if args.get("prefix"):
                return folium.Icon(**args)
            return folium.Icon(color=args.get("color","blue"), icon=args.get("icon","info-sign"))
    args = ICON_MAP.get(fallback, ICON_MAP["point_of_interest"])
    if args.get("prefix"):
        return folium.Icon(**args)
    return folium.Icon(color=args.get("color","cadetblue"), icon=args.get("icon","map-marker"))

def collect_recommendations_by_type(
    path: List[Tuple[float,float]],
    type_counts: Dict[str,int],
    base_radius_m: float = 3000,
    max_results_per_query: int = 20,
    prefer_open_now: bool = False,
    corridor_width_m: float = 5000,
    samples_per_chunk: int = 3,
    min_user_ratings: int = 50
) -> Dict[str, List[dict]]:
    results: Dict[str, List[dict]] = {}
    global_seen: set[str] = set()  # prevent duplicates across categories

    for typ, n in type_counts.items():
        if n <= 0:
            results[typ] = []
            continue

        chunks = split_path(path, n)
        picks: List[dict] = []
        local_seen: set[str] = set()

        for chunk in chunks:
            center = midpoint_of_chunk(chunk)
            winner: Optional[dict] = None

            for mult in (1, 2, 3):  # progressive radius expansion
                radius = base_radius_m * mult
                probes = _sample_points(chunk, samples_per_chunk)
                candidates: List[dict] = []

                for lat, lng in probes:
                    try:
                        found = places_nearby(lat, lng, radius, max_results_per_query,
                                              included_types=[typ])
                    except requests.RequestException:
                        found = []

                    for p in found:
                        pid = p.get("id")
                        if not pid or pid in local_seen or pid in global_seen:
                            continue
                        loc = p.get("location") or {}
                        plat, plng = loc.get("latitude"), loc.get("longitude")
                        if plat is None or plng is None:
                            continue
                        # corridor filter
                        if _min_distance_to_polyline_m((plat, plng), chunk) <= corridor_width_m:
                            candidates.append(p)

                if candidates:
                    winner = pick_best_place(
                        candidates, center,
                        prefer_open_now=prefer_open_now,
                        min_user_ratings=min_user_ratings
                    )
                    if winner:
                        break

            if winner:
                pid = winner["id"]
                local_seen.add(pid)
                global_seen.add(pid)
                picks.append(winner)
            else:
                picks.append({})  # keep slot for count

        results[typ] = picks

    return results

# --------------------------- Map rendering ---------------------------

def _format_opening_hours_html(place: dict) -> str:
    oh_now = ((place.get("currentOpeningHours") or {}).get("openNow"))
    wd = ((place.get("regularOpeningHours") or {}).get("weekdayDescriptions")) or []
    badge = ""
    if oh_now:
        badge = "<div style='margin-bottom:6px'><span style='color:#0a0'>● Open now</span></div>"
    elif oh_now is False:
        badge = "<div style='margin-bottom:6px'><span style='color:#a00'>● Closed now</span></div>"
    if not wd:
        return badge + "<div>Hours: n/a</div>"
    # detect 24/7
    unique = {s.split(":",1)[1].strip().lower() for s in wd if ":" in s}
    if len(unique) == 1 and next(iter(unique)).startswith("open 24"):
        return badge + "<div><b>Open 24/7</b></div>"
    # compact weekday/weekend
    days = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    parsed = []
    for s in wd:
        if ":" in s:
            d, h = s.split(":",1)
            parsed.append((d.strip(), h.strip()))
    def _hours_for(names):
        vals = [h for d,h in parsed if d in names]
        return vals[0] if vals and all(h==vals[0] for h in vals) else None
    wk = _hours_for(days[:5]); we = _hours_for(days[5:])
    if wk and we:
        return badge + f"<div>Mon–Fri: {wk}<br>Sat–Sun: {we}</div>"
    return badge + "<div>" + "<br>".join(wd) + "</div>"

def _build_map(path: List[Tuple[float,float]],
               origin_ll: Tuple[float,float],
               destination_ll: Tuple[float,float],
               recos: Dict[str, List[dict]],
               requested_recos: Dict[str, int]) -> folium.Map:
    mid = path[len(path)//2]
    m = folium.Map(location=mid, zoom_start=6, tiles=None, control_scale=True)

    # Basemaps
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        name="Satellite", attr="Satellite", max_zoom=19, opacity=0.90
    ).add_to(m)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
        name="Labels", attr="Points of Interest", overlay=True, control=True, max_zoom=20, opacity=0.95
    ).add_to(m)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{z}/{y}/{x}",
        name="Roads", attr="Tiles © Esri — Esri, HERE, Garmin, (c) OpenStreetMap contributors, and the GIS user community",
        overlay=True, control=True, max_zoom=20, opacity=0.75
    ).add_to(m)

    MiniMap(toggle_display=True).add_to(m)
    Fullscreen().add_to(m)
    MeasureControl(primary_length_unit='kilometers').add_to(m)

    # Route styling
    folium.PolyLine(path, weight=10, color="#ffffff", opacity=0.9).add_to(m)
    route_line = folium.PolyLine(path, weight=5, color="#00c2ff", opacity=1.0)
    route_line.add_to(m)
    PolyLineTextPath(
        route_line, "   ▶   ", repeat=True, offset=8,
        attributes={"fill": "#00c2ff", "font-weight": "bold", "font-size": "12"}
    ).add_to(m)

    # Pins
    folium.Marker(
        origin_ll, tooltip="Origin",
        icon=BeautifyIcon(icon_shape="marker", border_color="#2ecc71", text_color="#2ecc71",
                          icon="play", prefix="fa", background_color="#eafff3")
    ).add_to(m)
    folium.Marker(
        destination_ll, tooltip="Destination",
        icon=BeautifyIcon(icon_shape="marker", border_color="#e74c3c", text_color="#e74c3c",
                          icon="flag-checkered", prefix="fa", background_color="#ffecec")
    ).add_to(m)

    # Layers per category
    for typ, picks in recos.items():
        layer_name = f"{typ} (requested {requested_recos.get(typ, 0)})"
        cluster = MarkerCluster(name=layer_name).add_to(m)
        for p in picks:
            if not p:
                continue
            loc = p.get("location") or {}
            plat, plng = loc.get("latitude"), loc.get("longitude")
            if plat is None or plng is None:
                continue
            name = (p.get("displayName") or {}).get("text", "Place")
            addr = p.get("formattedAddress", "")
            rating = p.get("rating")
            rcnt = p.get("userRatingCount")
            price = p.get("priceLevel")
            uri = p.get("googleMapsUri")

            lines = [f"<b>{name}</b>", addr, _format_opening_hours_html(p)]
            if rating is not None:
                star = f"{float(rating):.1f}" if isinstance(rating, (int, float)) else rating
                extra = f" ({rcnt})" if rcnt not in (None, 0) else ""
                lines.append(f"Rating: {star} ⭐{extra}")
            if price is not None:
                try:
                    lines.append("Price: " + ("$" * (int(price) + 1)))  # 0=$ … 4=$$$$$
                except Exception:
                    pass
            if uri:
                lines.append(f'<a href="{uri}" target="_blank">Open in Google Maps</a>')

            folium.Marker(
                [plat, plng],
                tooltip=name,
                popup="<br>".join(lines),
                icon=_icon_for_place(p, fallback=typ),
            ).add_to(cluster)

    folium.LayerControl(collapsed=False).add_to(m)

    # Fit bounds
    all_pts = path + [
        (p["location"]["latitude"], p["location"]["longitude"])
        for plist in recos.values() for p in plist if p and p.get("location")
    ]
    if all_pts:
        lats = [pt[0] for pt in all_pts]; lngs = [pt[1] for pt in all_pts]
        m.fit_bounds([[min(lats), min(lngs)], [max(lats), max(lngs)]])
    return m

# --------------------------- Public callable ---------------------------

def build_route_map(
    origin: str,
    destination: str,
    *,
    vehicle_emission_type: str = "GASOLINE",
    requested_recos: Optional[Dict[str,int]] = None,
    # search/selection knobs
    search_radius: float = 3000,         # initial radius (m), expands x2 & x3 if needed
    prefer_open_now: bool = False,
    corridor_width_m: float = 5000,      # accept POIs within this distance (m) from route
    samples_per_chunk: int = 3,          # probe points per chunk
    min_user_ratings: int = 50,          # filter by number of reviews
    # output
    output_html: str = OUTPUT_HTML_DEFAULT
) -> str:
    """
    Returns: path to the saved HTML map.
    """
    if not API_KEY:
        raise RuntimeError("Set GOOGLE_MAPS_API_KEY environment variable.")


    # 1) Route
    path = compute_route(origin, destination, vehicle_emission_type)
    if len(path) < 2:
        raise RuntimeError("Route too short to render")

    # 2) Per-type recommendations with corridor filtering and global deduplication
    requested_recos = requested_recos or {}
    recos = collect_recommendations_by_type(
        path,
        requested_recos,
        base_radius_m=search_radius,
        max_results_per_query=20,
        prefer_open_now=prefer_open_now,
        corridor_width_m=corridor_width_m,
        samples_per_chunk=samples_per_chunk,
        min_user_ratings=min_user_ratings
    )

    total_route_km, poi_ann = summarize_poi_distances_along_route(path, recos, requested_recos)
    try:
        import csv
        with open("poi_consecutive_distances.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["index", "name", "type", "gap_km", "along_km", "total_route_km"])
            for i, p in enumerate(poi_ann, 1):
                gap_km = float(p.get("gap_km", 0.0))
                along_km = float(p.get("along_m", 0.0)) / 1000.0
                w.writerow([i,
                            p.get("name", ""),
                            p.get("type", "point_of_interest"),
                            f"{gap_km:.3f}",
                            f"{along_km:.3f}",
                            f"{total_route_km:.3f}"])
        print("Saved: poi_consecutive_distances.csv")
    except Exception as e:
        print("CSV write skipped:", e)

    # 3) Render & save
    origin_ll = get_location_coordinates(origin)
    destination_ll = get_location_coordinates(destination)
    m = _build_map(path, origin_ll, destination_ll, recos, requested_recos)
    _annotate_distances_on_map(m, poi_ann, total_route_km)
    m.save(output_html)
    return output_html

html_path = build_route_map(
    origin="Iasi",
    destination="Paris",
    vehicle_emission_type="ELECTRIC",
    requested_recos={"restaurant": 6, "gas_station": 4, "electric_vehicle_charging_station": 3, "tourist_attraction": 4},
    search_radius=12000,
    prefer_open_now=True,
    corridor_width_m=6000,
    samples_per_chunk=3,
    min_user_ratings=50,
    output_html="my_trip_map.html"
)
print("Saved:", html_path)
