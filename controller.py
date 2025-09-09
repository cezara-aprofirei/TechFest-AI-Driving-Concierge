import auto_features_recommend
import train_ev_ice
import wear_estimation
import find_route
import os
from typing import Any, Tuple, List, Dict, Optional

OUTPUT_HTML_DEFAULT = "route_pois_map.html"
API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")



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
    route = find_route.get_route_info(origin, destination, vehicle_emission_type)
    path = find_route.compute_path_from_polyline(route)
    total_time = find_route.get_route_duration(route)
    if len(path) < 2:
        raise RuntimeError("Route too short to render")
    
    #AICI AM FACUT MODIFICARI!!!!!!
    #
    #
    #
    total_distance = find_route.get_route_distance_km(route)
    stop_recommendations_dict = auto_features_recommend.main() #returns a str-int dict with place type and number
    print(total_distance)
    print(stop_recommendations_dict)
    #exit()
    fuel_recommendation_dict = train_ev_ice.main(total_distance//1000) 

    print(total_distance)
    print(stop_recommendations_dict)
    print(fuel_recommendation_dict)


    mapping = {
        "Restaurant": "restaurant",
        "Gas Station": "gas_station",
        "Shopping": "shopping_mall",
        "Tourist Attraction": "tourist_attraction",
        "Hotel":"hotel",
        "Rest Area": "rest_stop"
    }

    mapped_recommendations = {mapping.get(k, k): v for k, v in stop_recommendations_dict.items()}

    requested_recos = {**mapped_recommendations, **fuel_recommendation_dict}

    ratio =  total_distance/1000000
    for k, v, in requested_recos.items():
        if k not in ["gas_station", "electric_vehicle_charging_station"]:
            requested_recos[k] = int(v*ratio)
        # if vehicle_emission_type == "ELECTRIC":
        #     requested_recos["gas_station"] = 0
        # if vehicle_emission_type == "GASOLINE":
        #     requested_recos["electric_vehicle_charging_station"] = 0

    # 2) Per-type recommendations with corridor filtering and global deduplication

    recos = find_route.collect_recommendations_by_type(
        path,
        requested_recos,
        base_radius_m=search_radius,
        max_results_per_query=20,
        prefer_open_now=prefer_open_now,
        corridor_width_m=corridor_width_m,
        samples_per_chunk=samples_per_chunk,
        min_user_ratings=min_user_ratings
    )

    total_route_km, poi_ann = find_route.summarize_poi_distances_along_route(path, recos, requested_recos)

    sum_of_km_in_gaps = 0 

    try:
        import csv
        with open("poi_consecutive_distances.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([ "kilometers_since_last_stop", "stop_category"])
            for i, p in enumerate(poi_ann, 1):
                gap_km = float(p.get("gap_km", 0.0))
                sum_of_km_in_gaps += gap_km
                w.writerow([f"{gap_km:.3f}", p.get("type", "point_of_interest")])
            last_row_of_csv_gaps = total_distance/1000 - sum_of_km_in_gaps
            w.writerow([f"{last_row_of_csv_gaps:.3f}", "restaurant"])
        print("Saved: poi_consecutive_distances.csv")
    except Exception as e:
        print("CSV write skipped:", e)

    

    ##call the wear function to get the wear value
    wear = wear_estimation.return_wear()

    # 3) Render & save
    origin_ll = find_route.get_location_coordinates(origin)
    destination_ll = find_route.get_location_coordinates(destination)

    m = find_route._build_map(path, origin_ll, destination_ll, recos, requested_recos)

    find_route._annotate_distances_on_map(m, poi_ann, total_route_km, total_time, str(wear))
    m.save(output_html)
    return output_html


##call the function
html_path = build_route_map(
    origin="Iasi",
    destination="Paris",
    vehicle_emission_type="GASOLINE", #GASOLINE or ELECTRIC
    search_radius=12000,
    prefer_open_now=True,
    corridor_width_m=6000,
    samples_per_chunk=3,
    min_user_ratings=50,
    output_html="my_trip_map.html"
)