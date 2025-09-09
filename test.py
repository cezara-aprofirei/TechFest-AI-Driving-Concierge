import auto_features_recommend

stop_recommendations_dict = auto_features_recommend.main()

mapping = {
        "Restaurant": "restaurant",
        "Gas Station": "gas_station",
        "Shopping": "shopping_mall",
        "Tourist Attraction": "tourist_attraction",
        "Hotel":"hotel",
        "Rest Area": "rest_stop"
    }

mapped_recommendations = {mapping.get(k, k): v for k, v in stop_recommendations_dict.items()}
print("####################################3")
for k, v in mapped_recommendations.items():
    print(f"{k}: {v}")