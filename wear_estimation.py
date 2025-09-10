# stop_level_wear_model_equiv_km.py
import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score
import joblib
import csv

def return_wear(stop_data):

# ---------- Config ----------
    INPUT_CSV = Path("trip_recommendation_service_dataset.csv")
    MODEL_PATH = Path("stop_level_wear_per_km_model.pkl")
    
    # ---------- 1) Load dataset ----------
    df = pd.read_csv(INPUT_CSV)
    
    # Guard against zero/negative distances
    df = df[df["kilometers_since_last_stop"] > 0].copy()
    
    # Target transformation: wear per km
    df["wear_per_km"] = df["wear"] / df["kilometers_since_last_stop"]
    
    # Features and target
    X = df[["stop_duration_minutes", "kilometers_since_last_stop", "stop_category"]]
    y = df["wear_per_km"]
    
    # ---------- 2) Preprocessing ----------
    categorical_features = ["stop_category"]
    numeric_features = ["stop_duration_minutes", "kilometers_since_last_stop"]
    
    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_features),
            ("num", "passthrough", numeric_features),
        ]
    )
    
    # ---------- 3) Build Pipeline ----------
    model = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("regressor", RandomForestRegressor(n_estimators=200, random_state=42))
        ]
    )
    
    # ---------- 4) Train/Test split ----------
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    
    # ---------- 5) Train ----------
    model.fit(X_train, y_train)
    
    # ---------- 6) Evaluate on wear_per_km ----------
    y_pred = model.predict(X_test)
    mse = mean_squared_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    
    print("=== Wear-per-km Model ===")
    print(f"Train samples: {len(X_train)}, Test samples: {len(X_test)}")
    print(f"MSE (wear_per_km): {mse:.6f}")
    print(f"R^2 (wear_per_km): {r2:.4f}")
    
    # Optional: also evaluate equivalent-km error on held-out set just for intuition
    test_km = X_test["kilometers_since_last_stop"].to_numpy()
    eq_km_true = (y_test.to_numpy() * test_km)
    eq_km_pred = (y_pred * test_km)
    eq_km_mse = mean_squared_error(eq_km_true, eq_km_pred)
    print(f"MSE (equivalent km per segment): {eq_km_mse:.4f}")
    
    # ---------- 7) Save model ----------
    joblib.dump(model, MODEL_PATH)
    print(f"Model saved to: {MODEL_PATH.resolve()}")
    
    # ---------- 8) Inference on your route (poi_consecutive_distances.csv) ----------
    # Category mapping for your POIs
    mapping = {
        "restaurant": "Restaurant",
        "gas_station": "Gas Station",
        "shopping_mall": "Shopping",
        "tourist_attraction": "Tourist Attraction",
        "hotel": "Hotel",
        "rest_stop": "Rest Area",
        "electric_vehicle_charging_station": "Restaurant",
    }
    
    # Build the test/inference DataFrame from your POI distances file
    rows = []

    # Assuming results is the dictionary you built earlier
    for km, stop in zip(stop_data["kilometers_since_last_stop"], stop_data["stop_category"]):
        rows.append({
            "kilometers_since_last_stop": float(km),
            "stop_category": mapping.get(stop, stop),
            "stop_duration_minutes": None
        })

    test_data = pd.DataFrame(rows)

    
    # Fill stop_duration_minutes using a simple rule; default 30
    dur_map = {"Restaurant": 55, "Shopping": 120, "Hotel": 600}
    test_data["stop_duration_minutes"] = (
        test_data["stop_duration_minutes"]
        .fillna(test_data["stop_category"].map(dur_map).fillna(30))
    )
    
    # ---------- 9) Predict wear_per_km then convert to equivalent km ----------
    pred_wear_per_km = model.predict(test_data)
    pred_equiv_km = pred_wear_per_km * test_data["kilometers_since_last_stop"].to_numpy()
    
    test_data = test_data.assign(
        predicted_wear_per_km=pred_wear_per_km,
        predicted_equivalent_km=pred_equiv_km
    )
    
    # ---------- 10) Summarize the trip ----------
    actual_km = float(test_data["kilometers_since_last_stop"].sum())
    total_equiv_km = float(test_data["predicted_equivalent_km"].sum())
    wear_factor = (total_equiv_km / actual_km) if actual_km > 0 else np.nan
    
    print("\n=== Equivalent Distance Analysis ===")
    print(f"Actual distance driven: {actual_km:.0f} km")
    print(f"Equivalent distance (based on wear): {total_equiv_km:.0f} km") #print this one
    print(f"Extra wear factor: {wear_factor:.2f}x")
    
    # Optional: show per-stop preview
    print("\n--- Per-stop preview (first 10 rows) ---")
    print(test_data.head(10)[[
        "kilometers_since_last_stop", "stop_category", "stop_duration_minutes",
        "predicted_wear_per_km", "predicted_equivalent_km"
    ]].round(3))

    return round(total_equiv_km,1)