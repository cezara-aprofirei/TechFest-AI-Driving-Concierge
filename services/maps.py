# -------------------------------------------------
# services/maps.py
#
# Purpose:
# - Talk to Google Maps Platform:
#     * Routes API -> get a driving route + encoded polyline
#     * Places API (New) -> find places ALONG that route
# - Return clean Python data the UI can work with.
#
# Why this separation?
# - Keeps API logic out of app.py (easier to test and reuse)
# - Makes it simple to swap in another provider later (OSRM/Overpass)
# -------------------------------------------------

import requests
from typing import Dict, List, Any, Optional
from utils.settings import GOOGLE_MAPS_API_KEY

# Base endpoints we call
ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
PLACES_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"


def parse_duration_seconds(d: str) -> int:
    """
    Google returns durations as strings like '165s'.
    Convert that to an int (seconds). If anything is weird, return 0.
    """
    try:
        return int(str(d).replace("s", ""))
    except Exception:
        return 0


def compute_route_polyline(origin_str: str, dest_str: str) -> Dict[str, Any]:
    """
    Ask the Routes API for a route between the origin and destination.

    Inputs:
      - origin_str / dest_str: freeform addresses or 'City, Country'
        (Google will geocode them).

    Returns a dict with:
      - polyline: encoded path for the entire route (we draw this on the map)
      - distance_m: total distance (meters)
      - duration_s: total duration (seconds)

    Notes:
      - We use X-Goog-FieldMask to request ONLY what we need (faster + cheaper).
      - TRAFFIC_AWARE: gives us realistic times when available.
      - We do NOT depend on Streamlit here — just pure Python (easier to test).
    """
    if not GOOGLE_MAPS_API_KEY:
        raise RuntimeError("Missing GOOGLE_MAPS_API_KEY in .env")

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_MAPS_API_KEY,
        # Ask only for the fields we actually use (saves quota and latency)
        "X-Goog-FieldMask": "routes.distanceMeters,routes.duration,routes.polyline.encodedPolyline,routes.legs"
    }
    body = {
        "origin": {"address": origin_str},
        "destination": {"address": dest_str},
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
        "computeAlternativeRoutes": False,
        "units": "METRIC"
    }

    # Make the HTTP call
    resp = requests.post(ROUTES_URL, headers=headers, json=body, timeout=30)
    resp.raise_for_status()  # raise if 4xx/5xx

    # Pull the first route (Routes API can return multiple)
    route = resp.json()["routes"][0]

    # Return a minimal, UI-friendly dict
    return {
        "polyline": route["polyline"]["encodedPolyline"],
        "distance_m": route.get("distanceMeters", 0),
        "duration_s": parse_duration_seconds(route.get("duration", "0s"))
    }


def places_along_route(polyline: str, text_query: str, limit: int = 6) -> List[Dict[str, Any]]:
    """
    Use Places API (New) Text Search with Search Along Route.

    Inputs:
      - polyline: the encoded path from compute_route_polyline()
      - text_query: short search term (e.g., 'EV charging station', 'gas station', 'coffee')
      - limit: max number of results to request

    What makes this powerful:
      - We pass the route polyline to 'searchAlongRouteParameters', so Google
        returns places that are *actually on your way* (not random detours).
      - We request 'routingSummaries' which include tiny legs:
           * leg[0]: origin → place
           * leg[1]: place → destination
        That lets us estimate the extra **detour time** for each place.

    Returns:
      A sorted list of places (shortest detour first), each item containing:
        - id, name, address, (lat, lng), rating, priceLevel, primaryType
        - detour_s: seconds from origin to place (used as "minutes into trip")
        - to_dest_s: seconds from place to destination
        - directionsUri: Google directions deep link for that place
    """
    if not GOOGLE_MAPS_API_KEY:
        raise RuntimeError("Missing GOOGLE_MAPS_API_KEY in .env")

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_MAPS_API_KEY,
        # Ask for place basics + routingSummaries (so we can rank by detour)
        "X-Goog-FieldMask": (
            "places.id,places.displayName,places.formattedAddress,places.location,"
            "places.rating,places.priceLevel,places.primaryType,routingSummaries"
        )
    }
    body = {
        "textQuery": text_query,
        "maxResultCount": limit,
        # Magic: restrict to places along the given route polyline
        "searchAlongRouteParameters": {"polyline": {"encodedPolyline": polyline}}
    }

    resp = requests.post(PLACES_TEXT_SEARCH_URL, headers=headers, json=body, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    # Lists are parallel: places[i] corresponds to routingSummaries[i]
    places = data.get("places", [])
    summaries = data.get("routingSummaries", [])

    results: List[Dict[str, Any]] = []
    for i, p in enumerate(places):
        rs = summaries[i] if i < len(summaries) else {}
        legs = rs.get("legs", [])
        leg0 = legs[0] if len(legs) > 0 else {}

        results.append({
            "id": p.get("id"),
            "name": p.get("displayName", {}).get("text", ""),
            "address": p.get("formattedAddress", ""),
            "lat": p.get("location", {}).get("latitude"),
            "lng": p.get("location", {}).get("longitude"),
            "rating": p.get("rating"),
            "priceLevel": p.get("priceLevel"),
            "primaryType": p.get("primaryType"),

            # Treat leg0.duration as "minutes into the trip" to reach this stop.
            "detour_s": parse_duration_seconds(leg0.get("duration", "0s")),

            # Optional: leg1 is place → destination (can be handy for ETA to destination).
            "to_dest_s": parse_duration_seconds(legs[1]["duration"]) if len(legs) > 1 and "duration" in legs[1] else None,

            # Handy directions link that Google returns in the routing summary.
            "directionsUri": rs.get("directionsUri")
        })

    # Sort by shortest detour (i.e., "easiest stop"); None values go to the end
    results.sort(key=lambda x: (x["detour_s"] if x["detour_s"] is not None else 999999))
    return results

'''
How this integrates with the rest of the app
    compute_route_polyline() is called first in app.py → returns a polyline string (the route).
    That polyline and a search query go into places_along_route() → returns a ranked list of stops.
    The UI (ui/maps_embed.render_map) draws the polyline on the map and pins the places.
    The LLM planner (services/llm.extract_intent) decides the text_query (e.g., “EV charging station”).
'''