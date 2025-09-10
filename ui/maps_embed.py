# -------------------------------------------------
# ui/maps_embed.py
#
# Purpose:
# - Render a Google Map inside Streamlit.
# - Draw the route polyline.
# - Drop markers for the recommended places along the route.
#
# How it works:
# 1) We prepare a minimal JSON payload (polyline + places) in Python.
# 2) We base64-encode that payload to safely embed it into an HTML <script>.
# 3) In the browser, we decode it, initialize the map, decode the polyline,
#    draw it, and create markers with info windows.
#
# Why base64?
# - Embedding raw JSON in a JS string can break if it contains special chars.
# - Base64 ensures the payload is safely transported into the script.
# -------------------------------------------------

import json, base64
import streamlit as st


def render_map(google_api_key: str, polyline: str, places: list[dict]):
    """
    Render the interactive map.

    Parameters:
      - google_api_key: your Google Maps JavaScript API key.
      - polyline: encoded polyline string from the Routes API.
      - places: list of dicts with keys like:
          {
            "name": str,
            "lat": float,
            "lng": float,
            "address": str,
            "rating": float | None,
            "detour_s": int | None,
            "directionsUri": str | None
          }

    Notes:
      - We convert detour seconds to minutes here so the JS stays simple.
      - We filter out places missing lat/lng (can happen if API returns partial data).
    """

    # Prepare a compact payload for the browser:
    #  - polyline to draw the route
    #  - cleaned list of places with only fields the JS needs
    payload = {
        "polyline": polyline,
        "places": [
            {
                "name": p["name"],
                "lat": p["lat"],
                "lng": p["lng"],
                "address": p["address"],
                "rating": p.get("rating"),
                # Convert seconds → int minutes for display
                "detourMin": int(round((p.get("detour_s", 0) or 0) / 60)),
                "directionsUri": p.get("directionsUri"),
            }
            for p in places
            if p.get("lat") and p.get("lng")
        ],
    }

    # Base64-encode JSON payload so we can safely inline it in JS
    payload_b64 = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")

    # Build an HTML string that:
    #  - Creates a div for the map
    #  - Loads Google Maps JS (with the geometry library for polyline decoding)
    #  - Decodes our payload from base64 back to JSON
    #  - Decodes the encoded route polyline to a list of {lat, lng} points
    #  - Initializes the map, draws the polyline, fits bounds
    #  - Adds markers with info windows for each place
    html = f"""
<div id="map" style="height: 640px; width: 100%;"></div>
<script src="https://maps.googleapis.com/maps/api/js?key={google_api_key}&libraries=geometry"></script>
<script>
  // 1) Receive the Python data by decoding base64 → JSON
  const payload = JSON.parse(atob("{payload_b64}"));
  const routePolyline = payload.polyline;
  const places = payload.places;

  // 2) Decode an encoded polyline string into an array of Lat/Lng points.
  //    We implement a small decoder here so we don't rely on google.maps.geometry.encoding,
  //    keeping this self-contained and compatible.
  function decodePolyline(str, precision) {{
    let index=0, lat=0, lng=0, coords=[], shift=0, result=0, byte=null;
    const factor = Math.pow(10, precision || 5);
    while (index < str.length) {{
      shift=0; result=0;
      do {{ byte=str.charCodeAt(index++)-63; result|=(byte&0x1f)<<shift; shift+=5; }} while (byte>=0x20);
      const dlat=((result&1)?~(result>>1):(result>>1)); lat+=dlat;

      shift=0; result=0;
      do {{ byte=str.charCodeAt(index++)-63; result|=(byte&0x1f)<<shift; shift+=5; }} while (byte>=0x20);
      const dlng=((result&1)?~(result>>1):(result>>1)); lng+=dlng;

      coords.push({{lat: lat/factor, lng: lng/factor}});
    }}
    return coords;
  }}

  // 3) Initialize the map and draw everything
  function initMap() {{
    // Create the map; initial center doesn't matter because we fit to the route bounds
    const map = new google.maps.Map(document.getElementById("map"), {{
      zoom: 12,
      center: {{lat: 47.0105, lng: 28.8638}}, // Fallback center (e.g., Chișinău area)
      mapTypeId: "roadmap",         // default
      mapTypeControl: true,         // show control in the corner
      mapTypeControlOptions: {{
        style: google.maps.MapTypeControlStyle.HORIZONTAL_BAR,
        position: google.maps.ControlPosition.TOP_RIGHT
      }}
    }});

    // Decode the route polyline into a list of coordinates
    const path = decodePolyline(routePolyline, 5);

    // Draw the route line and fit the viewport to it
    if (path.length) {{
      const route = new google.maps.Polyline({{
        path,
        geodesic: true,
        strokeOpacity: 0.8,
        strokeWeight: 5
      }});
      route.setMap(map);

      const bounds = new google.maps.LatLngBounds();
      path.forEach(p => bounds.extend(p));
      map.fitBounds(bounds);
    }}

    // For each place, drop a marker + info window
    places.forEach(p => {{
      const marker = new google.maps.Marker({{
        map,
        position: {{lat: p.lat, lng: p.lng}}
      }});

      // Small HTML snippet shown when the marker is clicked
      const info = new google.maps.InfoWindow({{
        content: `<div style="max-width:240px">
          <strong>${{p.name}}</strong><br/>
          ${{p.address}}<br/>
          Detour ~ ${{p.detourMin}} min<br/>
          ${{p.directionsUri ? `<a href="${{p.directionsUri}}" target="_blank">Open directions</a>` : ""}}
        </div>`
      }});

      marker.addListener("click", () => info.open({{anchor: marker, map}}));
    }});
  }}

  // 4) Kick things off once the page loads
  window.onload = initMap;
</script>
"""

    # Finally, embed the HTML/JS block into the Streamlit app.
    # - height=680 sets the iframe's height
    # - scrolling=False keeps a clean look
    st.components.v1.html(html, height=680, scrolling=False)
