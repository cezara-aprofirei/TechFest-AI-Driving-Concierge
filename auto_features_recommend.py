#!/usr/bin/env python3
"""
auto_features_recommend.py

Usage:
  python auto_features_recommend.py \
      --driver_csv driver5_trip_data.csv \
      --full_csv trip_recommendation_service_dataset.csv \
      --model rf_stop_recommender.joblib \
      --driver_id 5 \
      --n_stops 6    # optional override; if omitted, inferred from history
"""
import argparse
import os
import sys
import pandas as pd
import numpy as np
from joblib import dump, load
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder

# ----------------------------
# Helpers to build features
# ----------------------------
CATS_TOD = ["Morning", "Afternoon", "Evening", "Night"]
CATS_WX  = ["Sunny", "Rainy", "Cloudy", "Snowy"]

def trip_feature_row(group: pd.DataFrame) -> pd.Series:
    feats = {
        "n_stops": len(group),
        "stop_duration_mean": group["stop_duration_minutes"].mean(),
        "stop_duration_std": group["stop_duration_minutes"].std(ddof=0),
        "km_since_last_mean": group["kilometers_since_last_stop"].mean(),
        "km_since_last_std": group["kilometers_since_last_stop"].std(ddof=0),
    }
    tod_share = group["time_of_day"].value_counts(normalize=True).reindex(CATS_TOD, fill_value=0.0).to_dict()
    feats.update({f"tod_share_{k}": v for k, v in tod_share.items()})
    weekend = {"Sat", "Sun"}
    feats["weekend_share"] = (group["day_of_week"].isin(weekend)).mean()
    wx_share = group["weather"].value_counts(normalize=True).reindex(CATS_WX, fill_value=0.0).to_dict()
    feats.update({f"wx_share_{k}": v for k, v in wx_share.items()})
    feats["km_per_stop"] = group["kilometers_since_last_stop"].sum() / max(len(group), 1)
    feats["driver_id"] = group["driver_id"].iloc[0]
    return pd.Series(feats)

def build_training_frames(full_df: pd.DataFrame):
    # Categories (targets) derived from full dataset
    categories = sorted(full_df["stop_category"].unique())

    # Aggregate features per (driver_id, trip_id)
    feature_df = (
        full_df.groupby(["driver_id", "trip_id"], as_index=False)
               .apply(trip_feature_row)
               .reset_index(drop=True)
    )

    # Targets: counts per category in that trip
    count_df = (
        full_df.groupby(["driver_id", "trip_id", "stop_category"])
               .size()
               .unstack(fill_value=0)
               .reindex(columns=categories, fill_value=0)
               .reset_index()
    )

    dataset = feature_df.merge(count_df, on=["driver_id", "trip_id"], how="inner")

    X_cols_numeric = [
        "n_stops", "stop_duration_mean", "stop_duration_std",
        "km_since_last_mean", "km_since_last_std",
        "tod_share_Morning", "tod_share_Afternoon", "tod_share_Evening", "tod_share_Night",
        "weekend_share",
        "wx_share_Sunny", "wx_share_Rainy", "wx_share_Cloudy", "wx_share_Snowy",
        "km_per_stop",
    ]

    X = dataset[X_cols_numeric + ["driver_id"]]
    Y = dataset[categories].astype(float)

    preprocess = ColumnTransformer(
        transformers=[
            ("num", "passthrough", X_cols_numeric),
            ("driver", OneHotEncoder(handle_unknown="ignore"), ["driver_id"]),
        ],
        remainder="drop",
    )
    return X, Y, preprocess, categories, X_cols_numeric, dataset

def infer_trip_profile_from_history(driver_df: pd.DataFrame) -> dict:
    """Compute a single feature row (typical trip profile) from raw driver history."""
    # Compute per-trip features first
    feats_per_trip = (
        driver_df.groupby(["driver_id", "trip_id"], as_index=False)
                 .apply(trip_feature_row)
                 .reset_index(drop=True)
    )

    # Typical trip profile = median across trips (robust to outliers)
    med = feats_per_trip.median(numeric_only=True).to_dict()

    # Ensure shares exist even if missing in data
    profile = {
        "n_stops": int(round(med.get("n_stops", max(1, len(driver_df) // 5)))),
        "stop_duration_mean": float(med.get("stop_duration_mean", driver_df["stop_duration_minutes"].mean())),
        "stop_duration_std": float(med.get("stop_duration_std", driver_df["stop_duration_minutes"].std(ddof=0))),
        "km_since_last_mean": float(med.get("km_since_last_mean", driver_df["kilometers_since_last_stop"].mean())),
        "km_since_last_std": float(med.get("km_since_last_std", driver_df["kilometers_since_last_stop"].std(ddof=0))),
        "tod_share_Morning": float(med.get("tod_share_Morning", 0.25)),
        "tod_share_Afternoon": float(med.get("tod_share_Afternoon", 0.25)),
        "tod_share_Evening": float(med.get("tod_share_Evening", 0.25)),
        "tod_share_Night": float(med.get("tod_share_Night", 0.25)),
        "weekend_share": float(med.get("weekend_share", 2/7)),
        "wx_share_Sunny": float(med.get("wx_share_Sunny", 0.5)),
        "wx_share_Rainy": float(med.get("wx_share_Rainy", 0.2)),
        "wx_share_Cloudy": float(med.get("wx_share_Cloudy", 0.3)),
        "wx_share_Snowy": float(med.get("wx_share_Snowy", 0.0)),
        "km_per_stop": float(med.get("km_per_stop", (driver_df["kilometers_since_last_stop"].sum() / max(len(driver_df),1)))),
        "driver_id": int(driver_df["driver_id"].iloc[0]),
    }
    return profile

def recommend_from_profile(pipe: Pipeline, categories, profile: dict, round_to_int=True):
    x_row = pd.DataFrame([profile])
    preds = pipe.predict(x_row)[0]
    preds = np.maximum(preds, 0.0)
    if round_to_int:
        preds = np.round(preds).astype(int)
    return dict(sorted(zip(categories, preds), key=lambda kv: kv[1], reverse=True))

# ----------------------------
# Main
# ----------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--driver_csv", required=True, help="Path to CSV with raw stops for ONE driver (e.g., driver5_trip_data.csv)")
    ap.add_argument("--full_csv", required=True, help="Path to full dataset CSV used for training (e.g., trip_recommendation_service_dataset.csv)")
    ap.add_argument("--model", default="rf_stop_recommender.joblib", help="Path to saved model pipeline (will train if not found)")
    ap.add_argument("--driver_id", type=int, required=True, help="Driver ID (used for sanity checks and encoding)")
    ap.add_argument("--n_stops", type=int, default=None, help="Optional override for expected stops in the new trip")
    args = ap.parse_args()

    # Load data
    full_df = pd.read_csv(args.full_csv)
    driver_df = pd.read_csv(args.driver_csv)

    # Sanity check
    if driver_df["driver_id"].nunique() != 1 or int(driver_df["driver_id"].iloc[0]) != args.driver_id:
        print(f"[Warning] driver_csv contains driver_id {driver_df['driver_id'].unique().tolist()} but --driver_id={args.driver_id}")

    # Build training frames / preprocess
    X, Y, preprocess, categories, X_cols_numeric, dataset = build_training_frames(full_df)

    # Model: load or train
    pipe = None
    if os.path.exists(args.model):
        try:
            pipe = load(args.model)
            # quick shape check by transforming a tiny slice
            _ = pipe.predict(X.iloc[[0]])
            print(f"[Info] Loaded model from {args.model}")
        except Exception as e:
            print(f"[Warning] Failed to load model ({e}). Retraining...")
            pipe = None

    if pipe is None:
        model = RandomForestRegressor(n_estimators=500, random_state=42, n_jobs=-1)
        pipe = Pipeline(steps=[("prep", preprocess), ("rf", model)])
        pipe.fit(X, Y)
        try:
            dump(pipe, args.model)
            print(f"[Info] Trained and saved model to {args.model}")
        except Exception as e:
            print(f"[Warning] Trained model but failed to save: {e}")

    # Build a typical trip profile from the driver's history
    profile = infer_trip_profile_from_history(driver_df)

    # Optional override for n_stops (e.g., planning a specific trip length)
    if args.n_stops is not None:
        profile["n_stops"] = int(args.n_stops)

    # Recommend counts per category
    recs = recommend_from_profile(pipe, categories, profile, round_to_int=True)

    # Pretty print
    print("\n=== Trip Profile (inferred) ===")
    for k, v in profile.items():
        if k != "driver_id":
            print(f"{k}: {v}")
    print(f"driver_id: {profile['driver_id']}")

    print("\n=== Recommended counts per category ===")
    for cat, c in recs.items():
        print(f"{cat}: {c}")

if __name__ == "__main__":
    main()
