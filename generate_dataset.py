import random

import pandas as pd


def calculate_risk_score(features: dict) -> float:
    temp = float(features.get("temperature", 25))
    humidity = float(features.get("humidity", 50))
    aqi = float(features.get("aqi", 50))
    altitude = float(features.get("altitude", 0))
    age = int(features.get("age", 30))
    bmi = float(features.get("bmi", 22))
    smoking = features.get("smoking", "No")
    alcohol = features.get("alcohol", "No")
    severity = features.get("severity", "low").lower()

    env = 0
    med = 0
    life = 0

    if temp > 40:
        env += 3
    elif temp > 35:
        env += 2
    elif temp < 5:
        env += 2

    if humidity > 85:
        env += 2

    if aqi > 200:
        env += 4
    elif aqi > 150:
        env += 3
    elif aqi > 100:
        env += 2

    if altitude > 3000:
        env += 3
    elif altitude > 2000:
        env += 2

    if severity == "high":
        med += 4
    elif severity == "moderate":
        med += 2

    if age > 60:
        med += 2
    if bmi > 30:
        med += 3
    elif bmi > 25:
        med += 2
    elif bmi < 18:
        med += 2

    if smoking == "Yes":
        life += 2
        if aqi > 100:
            life += 2

    if alcohol == "Yes":
        life += 1
        if temp > 35:
            life += 1

    env = min(env, 10)
    med = min(med, 10)
    life = min(life, 10)

    return round((0.4 * env) + (0.4 * med) + (0.2 * life), 1)


def generate_dataset(n_rows: int = 5000) -> pd.DataFrame:
    rows = []
    for _ in range(n_rows):
        sample = {
            "temperature": random.randint(0, 45),
            "humidity": random.randint(20, 100),
            "wind_speed": random.randint(0, 40),
            "aqi": random.randint(10, 300),
            "altitude": random.randint(0, 4000),
            "age": random.randint(5, 80),
            "bmi": round(random.uniform(16, 35), 1),
            "smoking": random.choice(["Yes", "No"]),
            "alcohol": random.choice(["Yes", "No"]),
            "severity": random.choice(["low", "moderate", "high"]),
        }
        sample["risk_score"] = calculate_risk_score(sample)
        rows.append(sample)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    dataset = generate_dataset(5000)
    dataset.to_csv("travel_health_dataset.csv", index=False)
    print(f"Dataset saved to travel_health_dataset.csv with {len(dataset)} rows.")
