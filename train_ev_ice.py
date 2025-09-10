#!/usr/bin/env python3
"""
Train two separate RandomForest regressors to predict 'consumption' for EV and ICE.

Features used:
- avg_speed_kmh (numeric)
- kilometers_since_last_stop (numeric)

Targets:
- consumption (kWh/100km for EV, L/100km for ICE)

Usage:
  python train_ev_ice.py --data path/to/augmented.csv --outdir models/

Outputs:
  - models/ev_consumption_model.pkl
  - models/ice_consumption_model.pkl
  - models/metrics.json  (MAE/R2 and sample counts for both models)
"""

import random
import csv
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split


def generate_tuples(n):
    # Generate n random integers between 50 and 130
    numbers = [random.randint(50, 130) for _ in range(n)]

    # Generate n random probability "weights"
    weights = [random.random() for _ in range(n)]
    total = sum(weights)
    
    # Normalize weights to sum to 100
    probabilities = [(w / total) * 100 for w in weights]
    
    # Round probabilities while keeping sum = 100
    rounded = [round(p, 2) for p in probabilities]
    diff = 100 - sum(rounded)
    rounded[0] += diff  # adjust first element to fix rounding error
    
    return list(zip(numbers, rounded))

def train_model_for_type(df: pd.DataFrame, vehicle_type: str, random_state: int = 42):
    """
    Train a RandomForestRegressor for a single vehicle type (EV or ICE).

    Returns:
        model, metrics_dict
    """
    # Filter by car type
    df_sub = df[df["car_type"] == vehicle_type].copy()
    if df_sub.empty:
        raise ValueError(f"No rows found for car_type='{vehicle_type}'.")

    # Basic validation
    needed_cols = {"avg_speed_kmh", "kilometers_since_last_stop", "consumption"}
    missing = needed_cols - set(df_sub.columns)
    if missing:
        raise ValueError(f"Missing columns for training: {missing}")

    # Prepare features/target
    X = df_sub[["avg_speed_kmh", "kilometers_since_last_stop"]].astype(float)
    y = df_sub["consumption"].astype(float)

    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=random_state
    )

    # Model (you can tune these)
    model = RandomForestRegressor(
        n_estimators=300,
        max_depth=None,
        min_samples_leaf=1,
        n_jobs=-1,
        random_state=random_state,
    )
    model.fit(X_train, y_train)

    # Evaluate
    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)

    metrics = {
        "vehicle_type": vehicle_type,
        "n_samples_total": int(len(df_sub)),
        "n_samples_train": int(len(X_train)),
        "n_samples_test": int(len(X_test)),
        "mae": float(mae),
        "r2": float(r2),
        "feature_importances": dict(
            zip(X.columns.tolist(), model.feature_importances_.tolist())
        ),
    }
    return model, metrics


def predict_consumption(model, avg_speed_kmh: float, kilometers_since_last_stop: float) -> float:
    """Single-row helper for inference."""
    X = np.array([[avg_speed_kmh, kilometers_since_last_stop]], dtype=float)
    return float(model.predict(X)[0])


def main(total_distance=2000):
    data="trip_recommendation_service_dataset.csv"
    random_state=42
    outdir = Path("models")
    outdir.mkdir(parents=True, exist_ok=True)

    # Load data
    df = pd.read_csv(data)

    # Train per type
    ev_model, ev_metrics = train_model_for_type(df, "EV", random_state)
    ice_model, ice_metrics = train_model_for_type(df, "ICE", random_state)

    # Save models
    ev_path = outdir / "ev_consumption_model.pkl"
    ice_path = outdir / "ice_consumption_model.pkl"
    joblib.dump(ev_model, ev_path)
    joblib.dump(ice_model, ice_path)

    # Save metrics
    metrics = {
        "EV": ev_metrics,
        "ICE": ice_metrics,
        "model_paths": {
            "EV": str(ev_path),
            "ICE": str(ice_path),
        },
    }
    with open(outdir / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    #total_distance = 1500  # De inlocuit de la Misnea AI
    n = total_distance // 90
    example_ev = 0.0
    example_ice = 0.0
    tuples = generate_tuples(n)
    for tuple in tuples:
        example_ev += predict_consumption(ev_model, avg_speed_kmh=tuple[0], kilometers_since_last_stop=total_distance*tuple[1]/100)
        example_ice += predict_consumption(ice_model, avg_speed_kmh=tuple[0], kilometers_since_last_stop=total_distance*tuple[1]/100)
    nr_fuelings = example_ice/50
    nr_chargings = example_ev/80

    dict = {
        "gas_station": int(nr_fuelings),
        "electric_vehicle_charging_station": int(nr_chargings)
        }
    
    for k, v in dict.items():
        print(f"{k}: {v}")
    return dict

    # with open("fueling_charging_stops.csv", "w", newline="") as f:
    #     writer = csv.writer(f)
    #     writer.writerow(["ICE", "EV"])  # header
    #     writer.writerow((int(nr_fuelings),int(nr_chargings)))

    ''' # Example inference (printed to console)
    example_ev = predict_consumption(ev_model, avg_speed_kmh=90, kilometers_since_last_stop=100)
    example_ice = predict_consumption(ice_model, avg_speed_kmh=110, kilometers_since_last_stop=60)
    print("Saved models to:")
    print(f"  EV : {ev_path}")
    print(f"  ICE: {ice_path}")
    print("\nMetrics (also in metrics.json):")
    print(json.dumps(metrics, indent=2))
    print("\nExample predictions:")
    print(f"  EV  (90 km/h, 100 km):  {example_ev:.2f}")
    print(f"  ICE (110 km/h, 60 km):  {example_ice:.2f}")'''


if __name__ == "__main__":
    main()

## how to run : python train_ev_ice.py --data trip_recommendation_service_dataset.csv --outdir models/