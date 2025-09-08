import os, requests, folium
from typing import Any
from folium.plugins import MarkerCluster, MiniMap, Fullscreen, MeasureControl, PolyLineTextPath, BeautifyIcon


API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

ORIGIN = (47.155, 27.586)                                      # (lat, lng)
INCLUDED_TYPES = ["gas_station"]          # Places types
OUTPUT_HTML = "route_pois_map.html"                            # Output HTML

ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
PLACES_TEXT_URL = "https://places.googleapis.com/v1/places:searchText"
PLACES_URL = "https://places.googleapis.com/v1/places:searchNearby"
GEOLOCATION_URL = "https://maps.googleapis.com/maps/api/geocode/json"


def get_location_coordinates(address):
    """Resolve a human-readable address to geographic coordinates (latitude and longitude)
    using the Google Geocoding API (JSON).

    Args:
        address (str): Address or place name (e.g., "Iași, Romania").

    Returns:
        tuple[float, float]: A pair (lat, lng) in decimal degrees when the geocoding succeeds;
        otherwise, a standard origin value is returned as a fallback.

    Raises:
        requests.HTTPError
        requests.RequestException
        ValueError
    """

    #--- Build query parameters ---#
    params = {"address": address, "key": API_KEY}

    #--- Call Geocoding endpoint and parse the response ---#
    response = requests.get(GEOLOCATION_URL, params=params)
    data = response.json()

    #--- Return the coordinates ---#
    if data["status"] == "OK":
        location = data["results"][0]["geometry"]["location"]
        return location["lat"], location["lng"]
    else:
        print("Error:", data["status"])
        return ORIGIN


def compute_route(origin, destination, vehicle_emission_type):
    """Compute a driving route between two places and return decoded coordinates.

    This function:
        1) Geocodes the free-text origin and destination into (latitude, longitude),
        2) Calls the Google Maps Routes API (computeRoutes) for a driving route,
        3) Decodes the route’s encoded polyline into a list of (latitude, longitude) tuples.

    Args:
        origin (str): Free-form origin (e.g., "Iași, Romania").
        destination (str): Free-form destination (e.g., "Vaslui, Romania").
        vehicle_emission_type (str): "DIESEL", "GASOLINE", "ELECTRIC", or "HYBRID".

    Returns:
        list[tuple[float, float]]: Decoded route path as (latitude, longitude) pairs.
        If the top-level route polyline is missing, leg polylines are concatenated.

    Raises:
        RuntimeError
        requests.HTTPError
        requests.RequestException
    """

    #--- Prepare headers for API call (use FieldMask for returning only certain results) ---#
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": "routes.polyline.encodedPolyline,routes.legs.polyline.encodedPolyline",
    }

    #--- Forward-geocode origin and destination into their corresponding latitude and longitude ---#
    origin_lat, origin_lng = get_location_coordinates(origin)
    dest_lat, dest_lng = get_location_coordinates(destination)

    #--- Build request payload ---#
    payload = {
        "origin": {
            "location": {
                "latLng": {
                    "latitude": origin_lat,
                    "longitude": origin_lng}
            }
        },
        "destination": {
            "location": {
                "latLng": {
                    "latitude": dest_lat,
                    "longitude": dest_lng
                }
            }
        },
        "routeModifiers": {
            "vehicleInfo": {
                "emissionType": vehicle_emission_type
            }
        },
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE_OPTIMAL",
        "polylineQuality": "HIGH_QUALITY",
        "polylineEncoding": "ENCODED_POLYLINE",
        "requestedReferenceRoutes": ["FUEL_EFFICIENT"]
    }

    #--- Call the Routes API; raise exception for non-success HTTP status ---#
    r = requests.post(ROUTES_URL, headers=headers, json=payload, timeout=30)
    r.raise_for_status()

    #--- Parse route and get polyline ---#
    routes = r.json().get("routes", [])
    if not routes:
        raise RuntimeError("No route returned")
    enc = routes[0].get("polyline", {}).get("encodedPolyline")
    if enc:
        return decode_polyline(enc)

    # Fallback - use individual leg polylines to construct route polyline ---#
    coordinates = []
    for leg in routes[0].get("legs", []):
        leg_enc = leg.get("polyline", {}).get("encodedPolyline")
        if leg_enc: coordinates += decode_polyline(leg_enc)

    #--- Error if polyline is not correctly found ---#
    if not coordinates: raise RuntimeError("No polyline found")
    return coordinates


def decode_polyline(encoded: str):
    """Decode a Google Encoded Polyline string into latitude/longitude pairs.

    Google’s polyline format encodes a path as a compact ASCII string. Each
    point is stored as a delta from the previous point, scaled by 1e5, and
    serialized with variable-length chunks using a continuation bit and
    ZigZag (signed) encoding.

    Args:
        encoded: The encoded polyline string (e.g., 'a~l~Fjk~uOwHJy@P').

    Returns:
        list[tuple[float, float]]: a list of (lat, lng) tuples in decimal degrees, in path order.

    Raises:
        IndexError
        ValueError
    """

    #--- Running index into the encoded string ---#
    idx = 0

    #--- Latitude, longitude pair
    lat = 0
    lng = 0

    #--- Output list: pairs of (lat, lng) ---#
    out: list[tuple[float, float]] = []

    #--- Process the encoded polyline ---#
    while idx < len(encoded):
        #--- Decode longitude delta ---#
        shift, result = 0, 0
        while True:
            #--- Get the original 6-bit chunk ---#
            b = ord(encoded[idx]) - 63
            idx += 1

            #--- Add lower 5 bits to the result with appropriate shift ---#
            result |= (b & 0x1f) << shift
            shift += 5

            #--- Continuation bit clear -> last chunk for this value ---#
            if b < 0x20: break

        #--- ZiZag decode: LSB is the sign bit
        dlat = ~(result >> 1) if result & 1 else (result >> 1)
        lat += dlat

        #--- Decode longitude delta ---#
        shift, result = 0, 0
        while True:
            b = ord(encoded[idx]) - 63; idx += 1
            result |= (b & 0x1f) << shift; shift += 5
            if b < 0x20: break
        dlng = ~(result >> 1) if result & 1 else (result >> 1)
        lng += dlng

        #--- Convert back from 1e-5 degrees and append ---#
        out.append((lat / 1e5, lng / 1e5))
    return out


def filter_open_now(places: list[dict]) -> list[dict]:
    out = []
    for p in places:
        oh = p.get("currentOpeningHours") or {}
        if oh.get("openNow"):
            out.append(p)
    return out


def places_nearby(lat, lng, search_radius, result_count):
    """Search for nearby places around a point using Google Places API.

    This function calls the Places API - places:searchNearby endpoint with a
    circular location restriction centered at the given latitude/longitude. It
    returns up to `resultCount` place objects.

    Args:
        lat (float): Latitude of the search center, in decimal degrees.
        lng (float): Longitude of the search center, in decimal degrees.
        search_radius (float): Search radius around the nearby places.
        result_count (int): The maximum number of places returned by the API call.

    Returns:
        list[dict]: A list of place dictionaries as returned by Places API.

    Raises:
        requests.HTTPError
        requests.RequestException
    """

    #--- Prepare headers for API call (use FieldMask for returning only certain results) ---#
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": (
            "places.id,places.displayName,places.formattedAddress,places.location,"
            "places.regularOpeningHours.weekdayDescriptions,"
            "places.currentOpeningHours.openNow,"  # <- add (optional but nice)
            "places.types,"  # <- add for icon colors
            "places.rating,places.googleMapsUri"
        )
    }

    #--- Build request payload
    #    Define circular search area  ---#
    payload: dict[str, Any] = {
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": lat,
                    "longitude": lng
                },
                "radius": float(search_radius) }
        },
        "maxResultCount": result_count
    }

    #--- Filter by point of interest type ---#
    if INCLUDED_TYPES:
        payload["includedTypes"] = INCLUDED_TYPES

    #--- Call the Places API; raise exception for non-success HTTP status ---#
    r = requests.post(PLACES_URL, headers=headers, json=payload, timeout=30)
    r.raise_for_status()

    #--- Extract the list of points of interest ---#
    return r.json().get("places", []) or []


def _format_opening_hours_html(place: dict) -> str:
    """Format opening hours returned by Google Maps Places API.

    Args:
        place (dict): A point of interest represented as dictionary.

    Returns:
        str: Opening hours string.
    """

    oh_now = ((place.get("currentOpeningHours") or {}).get("openNow"))
    wd = ((place.get("regularOpeningHours") or {}).get("weekdayDescriptions")) or []
    badge = ""
    if oh_now:
        badge = "<div style='margin-bottom:6px'><span style='color:#0a0'>● Open now</span></div>"
    elif oh_now is False:
        badge = "<div style='margin-bottom:6px'><span style='color:#a00'>● Closed now</span></div>"

    if not wd:
        return badge + "<div>Hours: n/a</div>"

    #--- Detect 24/7 ---#
    unique = {s.split(":",1)[1].strip().lower() for s in wd if ":" in s}
    if len(unique) == 1 and next(iter(unique)).startswith("open 24"):
        return badge + "<div><b>Open 24/7</b></div>"

    #--- Compact grouping: Mon–Fri on one line, weekend on one line ---#
    # Fallback: list all lines.
    days = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    parsed = []
    for s in wd:
        if ":" in s:
            day, hours = s.split(":",1)
            parsed.append((day.strip(), hours.strip()))

    #--- Weekday/weekend collapse ---#
    def _hours_for(names):
        vals = [h for d,h in parsed if d in names]
        return vals[0] if vals and all(h==vals[0] for h in vals) else None
    wk = _hours_for(days[:5])
    we = _hours_for(days[5:])
    if wk and we:
        return badge + f"<div>Mon–Fri: {wk}<br>Sat–Sun: {we}</div>"

    #--- Else show full list ---#
    return badge + "<div>" + "<br>".join(wd) + "</div>"


def _icon_for_place(p: dict) -> folium.Icon:
    """Select icon for singular POI.

    Args:
        p (dict): A point of interest represented as dictionary.

    Returns:
        folium.Icon: Icon representing the point of interest.
    """
    types = set(p.get("types") or [])

    if "electric_vehicle_charging_station" in types or "charging_station" in types:
        return folium.Icon(color="purple", icon="bolt", prefix="fa")
    if "gas_station" in types:
        return folium.Icon(color="green", icon="tint", prefix="fa")

    if "restaurant" in types:
        return folium.Icon(color="red", icon="cutlery", prefix="fa")
    if "cafe" in types:
        return folium.Icon(color="orange", icon="coffee", prefix="fa")
    if "tourist_attraction" in types or "point_of_interest" in types:
        return folium.Icon(color="blue", icon="info-sign")


    return folium.Icon(color="cadetblue", icon="map-marker")


def get_complete_route(origin, destination, vehicle_emission_type="GASOLINE", search_radius = 1000, max_pois = 10):
    """Build a route from origin to destination, fetch POIs along the way, and export a Folium map.

    Workflow:
        1) Compute a driving route (list of (lat, lng) points) via `compute_route`.
        2) Sample S evenly spaced points along the path (uses global SAMPLES_ALONG_ROUTE).
        3) For each sample point, call `places_nearby(..., max_pois)` to find places.
        4) De-duplicate results by place `id`.
        5) Render origin/destination, the route polyline, and POI markers.

    Args:
        origin (str): Free-form origin (e.g., "Iași, Romania").
        destination (str): Free-form destination (e.g., "Vaslui, Romania").
        vehicle_emission_type (str): "DIESEL", "GASOLINE", "ELECTRIC", or "HYBRID".
        search_radius (float): Search radius around the nearby places returned by the Places API.
        max_pois (int, optional): Maximum results to request per nearby call.
            The Places API typically caps page size at 20. Defaults to 10.

    Returns:
        None. Writes an interactive HTML map and prints the location.

    Raises:
        SystemExit
        RuntimeError / requests.RequestException
    """

    #--- Ensure valid key ---#
    if not API_KEY or API_KEY == "YOUR_API_KEY":
        raise SystemExit("Set GOOGLE_MAPS_API_KEY env var or replace API_KEY.")

    #--- 1) Compute the route geometry (list of (lat, lng) tuples) ---#
    path = compute_route(origin, destination, vehicle_emission_type)
    if len(path) < 2:
        raise SystemExit("Route too short.")

    #--- 2) Choose evenly spaced indices along the path to use as centers for Places 'nearby' queries (corridor sampling) ---#
    ides = [int((i+1) * len(path) / (max_pois+1)) for i in range(max_pois)]
    sample_pts = [path[i] for i in ides]


    #--- 3) Query nearby places around each sample point and de-duplicate by place id ---#
    seen, pois = set(), []
    for (lat,lng) in sample_pts:
        for p in places_nearby(lat, lng, search_radius, max_pois):
            place_id = p.get("id")
            if place_id and place_id not in seen:
                seen.add(place_id)
                pois.append(p)

#--- 4) Render interactive map with Folium ---#
    #--- Get start and destination longitude and latitude ---#
    origin_ll = get_location_coordinates(origin)
    destination_ll = get_location_coordinates(destination)

    #--- Center roughly at route midpoint ---#
    mid = path[len(path) // 2]
    m = folium.Map(location=mid, zoom_start=6, tiles=None, control_scale=True)

    #--- Satellite + labels/roads ---#
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        name="Satellite",
        attr="Satellite",
        max_zoom=19, opacity=0.90
    ).add_to(m)

    #--- Labels (cities/places) overlay ---#
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
        name="Labels",
        attr="Points of Interest",
        overlay=True, control=True, max_zoom=20, opacity=0.95
    ).add_to(m)

    #--- Roads overlay ---#
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{z}/{y}/{x}",
        name="Roads",
        attr="Tiles © Esri — Esri, HERE, Garmin, (c) OpenStreetMap contributors, and the GIS user community",
        overlay=True, control=True, max_zoom=20, opacity=0.75
    ).add_to(m)

    MiniMap(toggle_display=True).add_to(m)
    Fullscreen().add_to(m)
    MeasureControl(primary_length_unit='kilometers').add_to(m)

    #--- Route styling: white underlay + coloured line ---#
    folium.PolyLine(path, weight=10, color="#ffffff", opacity=0.9).add_to(m)
    # Main route
    route_line = folium.PolyLine(path, weight=5, color="#00c2ff", opacity=1.0)
    route_line.add_to(m)

    #--- Direction arrows along the route ---#
    PolyLineTextPath(
        route_line,
        "   ▶   ",  # repeated arrow symbol
        repeat=True,
        offset=8,
        attributes={"fill": "#00c2ff", "font-weight": "bold", "font-size": "12"}
    ).add_to(m)

    #--- Origin / Destination: nicer pins (BeautifyIcon) ---#
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

    #--- POIs: cluster + richer popups ---#
    cluster = MarkerCluster(name="Stops along the way").add_to(m)
    for p in pois:
        loc = p.get("location") or {}
        plat, plng = loc.get("latitude"), loc.get("longitude")
        if plat is None or plng is None:
            continue

        name = (p.get("displayName") or {}).get("text", "Place")
        addr = p.get("formattedAddress", "")
        rating = p.get("rating")
        uri = p.get("googleMapsUri")

        hours_html = _format_opening_hours_html(p)
        lines = [f"<b>{name}</b>", addr, hours_html]
        if rating is not None:
            lines.append(f"Rating: {rating} ⭐")
        if uri:
            lines.append(f'<a href="{uri}" target="_blank">Open in Google Maps</a>')
        popup_html = "<br>".join(lines)

        folium.Marker(
            [plat, plng],
            tooltip=name,
            popup=popup_html,
            icon=_icon_for_place(p),
        ).add_to(cluster)

    #--- Layer switcher ---#
    folium.LayerControl(collapsed=False).add_to(m)

    #--- Fit bounds to route + POIs ---#
    all_pts = path + [
        (p["location"]["latitude"], p["location"]["longitude"])
        for p in pois if p.get("location")
    ]
    if all_pts:
        lats = [pt[0] for pt in all_pts]
        lngs = [pt[1] for pt in all_pts]
        m.fit_bounds([[min(lats), min(lngs)], [max(lats), max(lngs)]])

    #--- Save and notify ---#
    m.save(OUTPUT_HTML)
    print(f"Saved map to {OUTPUT_HTML}")


get_complete_route("Iasi", "Paris", "ELECTRIC", 22000, 16)
