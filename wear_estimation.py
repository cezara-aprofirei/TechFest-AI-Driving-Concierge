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
mock_data = pd.DataFrame({
    "stop_duration_minutes": [5, 45, 120],
    "kilometers_since_last_stop": [50, 80, 150],
    "stop_category": ["Restaurant", "Shopping", "Hotel"]
})

mock_predictions = model.predict(mock_data)
print("\n=== Mock Predictions ===")
print(pd.DataFrame({
    "stop_duration_minutes": mock_data["stop_duration_minutes"],
    "kilometers_since_last_stop": mock_data["kilometers_since_last_stop"],
    "stop_category": mock_data["stop_category"],
    "predicted_wear": mock_predictions.round(2)
}))
