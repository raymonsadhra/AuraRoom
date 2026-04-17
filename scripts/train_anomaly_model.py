"""
Train AuraRoom's anomaly detector on synthetic room telemetry.

What this script does:
- Generates a synthetic dataset representing typical hackathon room activity.
- Trains an Isolation Forest on people count and audio level features.
- Saves both the dataset CSV and the trained model artifact to `data/`.

How it contributes to AuraRoom:
- Provides a reproducible, local-first bootstrap path for the anomaly model so
  the app can detect unusually busy or unusually quiet room conditions.
"""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
CSV_PATH = DATA_DIR / "synthetic_room_data.csv"
MODEL_PATH = DATA_DIR / "room_anomaly_model.pkl"


def build_dataset(random_seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(random_seed)

    normal_rows = 2000
    anomaly_rows = 100

    normal_people = np.clip(rng.normal(loc=15, scale=4.0, size=normal_rows), 0, 32)
    normal_audio = np.clip(rng.normal(loc=55, scale=7.0, size=normal_rows), 35, 75)

    anomaly_people = np.clip(rng.normal(loc=58, scale=6.0, size=anomaly_rows), 45, 90)
    anomaly_audio = np.clip(rng.normal(loc=88, scale=4.5, size=anomaly_rows), 80, 100)

    normal_df = pd.DataFrame(
        {
            "people_count": np.rint(normal_people).astype(int),
            "audio_energy": np.round(normal_audio, 2),
            "synthetic_label": "normal",
        }
    )
    anomaly_df = pd.DataFrame(
        {
            "people_count": np.rint(anomaly_people).astype(int),
            "audio_energy": np.round(anomaly_audio, 2),
            "synthetic_label": "anomaly",
        }
    )

    df = pd.concat([normal_df, anomaly_df], ignore_index=True)
    return df.sample(frac=1.0, random_state=random_seed).reset_index(drop=True)


def train_model(df: pd.DataFrame, random_seed: int = 42) -> IsolationForest:
    contamination = float((df["synthetic_label"] == "anomaly").mean())
    model = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        random_state=random_seed,
    )
    model.fit(df[["people_count", "audio_energy"]].to_numpy())
    return model


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    dataset = build_dataset()
    dataset.to_csv(CSV_PATH, index=False)

    model = train_model(dataset)
    joblib.dump(model, MODEL_PATH)

    print(f"Wrote dataset: {CSV_PATH}")
    print(f"Wrote model:   {MODEL_PATH}")
    print(dataset["synthetic_label"].value_counts().to_string())


if __name__ == "__main__":
    main()
