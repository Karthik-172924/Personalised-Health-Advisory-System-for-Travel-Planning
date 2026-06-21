import sys
import os
import pandas as pd
from pathlib import Path

# Add current directory to path
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

from ml_model import predict_risk_level

# Mock TOURIST_DB
def test_filtering():
    tourist_df = pd.read_csv(BASE_DIR / 'tourist_places.csv').fillna('')
    tourist_db = {}
    for _, row in tourist_df.iterrows():
        if row['city'] not in tourist_db:
            tourist_db[row['city']] = {
                'state': row['state'],
                'tourist_place': row['tourist_place'],
                'temperature': row['temperature'],
                'humidity': row['humidity'],
                'wind_speed': row['wind_speed'],
                'uv_index': row['uv_index'],
                'category': row['category'],
                'climate_type': row['climate_type'],
                'altitude': row.get('altitude', 0)
            }

    safe_places = []
    base_profile = {
        "disease_name": "None / Healthy", "severity": "None",
        "age": 30, "bmi": 22.0, "smoking": "No", "alcohol": "No", "altitude": 0
    }
    
    print("Testing Top Destinations Logic...")
    for city, info in tourist_db.items():
        feat = base_profile.copy()
        feat.update({
            "city": city,
            "temperature": info['temperature'],
            "humidity": info['humidity'],
            "wind_speed": info['wind_speed'],
            "uv_index": info['uv_index'],
            "aqi": 50,
            "altitude": info.get('altitude', 0)
        })
        
        lvl, score, _ = predict_risk_level(feat)
        if lvl == "Low":
            safe_places.append((city, score))
            
    safe_places = sorted(safe_places, key=lambda x: x[1])[:12]
    
    if safe_places:
        print(f"Success: Found {len(safe_places)} low-risk destinations.")
        for name, score in safe_places:
            print(f"- {name}: {score}")
    else:
        print("Warning: No low-risk destinations found in the current dataset.")

if __name__ == "__main__":
    test_filtering()
