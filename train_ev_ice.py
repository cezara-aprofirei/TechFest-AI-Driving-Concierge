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

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split


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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data",
        type=str,
        required=True,
        help="Path to the augmented CSV with columns: car_type, avg_speed_kmh, kilometers_since_last_stop, consumption",
    )
    parser.add_argument(
        "--outdir",
        type=str,
        default="models",
        help="Output directory for saved models and metrics",
    )
    parser.add_argument("--random_state", type=int, default=42)
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # Load data
    df = pd.read_csv(args.data)

    # Train per type
    ev_model, ev_metrics = train_model_for_type(df, "EV", random_state=args.random_state)
    ice_model, ice_metrics = train_model_for_type(df, "ICE", random_state=args.random_state)

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

    # Example inference (printed to console)
    example_ev = predict_consumption(ev_model, avg_speed_kmh=90, kilometers_since_last_stop=100)
    example_ice = predict_consumption(ice_model, avg_speed_kmh=110, kilometers_since_last_stop=60)
    print("Saved models to:")
    print(f"  EV : {ev_path}")
    print(f"  ICE: {ice_path}")
    print("\nMetrics (also in metrics.json):")
    print(json.dumps(metrics, indent=2))
    print("\nExample predictions:")
    print(f"  EV  (90 km/h, 100 km):  {example_ev:.2f}")
    print(f"  ICE (110 km/h, 60 km):  {example_ice:.2f}")


if __name__ == "__main__":
    main()

## how to run : python train_ev_ice.py --data trip_recommendation_service_dataset.csv --outdir models/