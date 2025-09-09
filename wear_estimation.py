# stop_level_wear_model.py
import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score
import joblib
import csv

# ---------- Config ----------
INPUT_CSV = Path("trip_recommendation_service_dataset.csv")
MODEL_PATH = Path("stop_level_wear_model.pkl")

# ---------- 1) Load dataset ----------
df = pd.read_csv(INPUT_CSV)

# Features and target
X = df[["stop_duration_minutes", "kilometers_since_last_stop", "stop_category"]]
y = df["wear"]

# ---------- 2) Preprocessing ----------
# One-hot encode categorical column stop_category
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

# ---------- 6) Evaluate ----------
y_pred = model.predict(X_test)
mse = mean_squared_error(y_test, y_pred)
r2 = r2_score(y_test, y_pred)

print("=== Stop-level Wear Prediction Model ===")
print(f"Train samples: {len(X_train)}, Test samples: {len(X_test)}")
print(f"MSE: {mse:.4f}")
print(f"R^2: {r2:.4f}")

# ---------- 7) Save model ----------
joblib.dump(model, MODEL_PATH)
print(f"Model saved to: {MODEL_PATH.resolve()}")

# ---------- 8) Test with Mock Data ----------
'''mock_data = pd.DataFrame({
    "stop_duration_minutes": [5, 45, 120],
    "kilometers_since_last_stop": [50, 80, 150],
    "stop_category": ["Restaurant", "Shopping", "Hotel"]
})'''

##iau doar dictionarul cu stop_category si fac mapare

mapping = {
    "restaurant": "Restaurant",
    "gas_station": "Gas Station",
    "shopping_mall": "Shopping",
    "tourist_attraction": "Tourist Attraction",
    "hotel": "Hotel",
    "rest_stop": "Rest Area", 
    "electric_vehicle_charging_station":"Restaurant"
}


rows = []
with open("poi_consecutive_distances.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader)  # Skip header
    for row in reader:
        rows.append({
            "kilometers_since_last_stop": float(row[0]),
            "stop_category": mapping.get(row[1], row[1]),
            "stop_duration_minutes": None  # or some default if needed
        })

test_data = pd.DataFrame(rows)

for row in test_data.itertuples():
    if pd.isna(row.stop_duration_minutes):
        if row.stop_category == "Restaurant":
            test_data.at[row.Index, "stop_duration_minutes"] = 55
        elif row.stop_category == "Shopping":
            test_data.at[row.Index, "stop_duration_minutes"] = 120
        elif row.stop_category == "Hotel":
            test_data.at[row.Index, "stop_duration_minutes"] = 600
        else:
            test_data.at[row.Index, "stop_duration_minutes"] = 30  # Default

predictions = model.predict(test_data)
print("\n=== Mock Predictions ===")
print(pd.DataFrame({
    "stop_duration_minutes": test_data["stop_duration_minutes"],
    "kilometers_since_last_stop": test_data["kilometers_since_last_stop"],
    "stop_category": test_data["stop_category"],
    "predicted_wear": predictions.round(2)
}))

sum = 0
for pred in predictions:
    sum += pred

def return_wear():
    print("\n=== Total Wear Prediction ===")
    print(f"Total predicted wear: {int(sum.round(0))}")
    return int(sum.round(0))

return_wear()