import sys
import os
import requests
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

# Add current directory to path
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

# Load Env
load_dotenv()
API_KEY = os.environ.get("OPENWEATHER_API_KEY", "")

from ml_model import predict_risk_level

def calculate_aqi(pm25):
    """Approximate PM2.5 to AQI conversion."""
    if pm25 <= 12: return 50 * (pm25 / 12)
    if pm25 <= 35.4: return 51 + (49 * (pm25 - 12.1) / (35.4 - 12.1))
    if pm25 <= 55.4: return 101 + (49 * (pm25 - 35.5) / (55.4 - 35.5))
    if pm25 <= 150.4: return 151 + (49 * (pm25 - 55.5) / (150.4 - 55.5))
    return 201 + (pm25 - 150.5)

def get_realtime_data(city: str):
    """Fetch live weather data if API key is available."""
    if not API_KEY or len(API_KEY) < 10:
        return None
    
    try:
        # Get coordinates
        geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&appid={API_KEY}"
        resp = requests.get(geo_url, timeout=5).json()
        if not resp: return None
        lat, lon = resp[0]['lat'], resp[0]['lon']
        
        # Get weather
        w_url = f"http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric"
        w_data = requests.get(w_url, timeout=5).json()
        
        # Get AQI
        aqi_url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}"
        aqi_data = requests.get(aqi_url, timeout=5).json()
        pm25 = aqi_data['list'][0]['components']['pm2_5']
        
        return {
            "temp": w_data['main']['temp'],
            "humidity": w_data['main']['humidity'],
            "wind": w_data['wind']['speed'] * 3.6,
            "aqi": calculate_aqi(pm25)
        }
    except Exception:
        return None

def test_all_destinations():
    # Load Data
    try:
        health_df = pd.read_csv(BASE_DIR / 'health.csv').fillna('')
        tourist_df = pd.read_csv(BASE_DIR / 'tourist_places.csv').fillna('')
    except Exception as e:
        print(f"Error loading CSV files: {e}")
        return

    # Get 'None / Healthy' profile
    healthy_disease = "None / Healthy"
    healthy_severity = "None"

    # Get a 'High' severity disease for comparison
    high_risk_row = health_df[health_df['severity'] == 'High'].head(1)
    high_disease = high_risk_row.iloc[0]['disease_name'] if not high_risk_row.empty else "Asthma"
    high_severity = "High"

    unique_cities = tourist_df.drop_duplicates(subset=['city']).head(15) # Test first 15 to avoid over-calling
    
    print(f"{'City':<15} | {'Source':<10} | {'Temp':<5} | {'Healthy Risk':<15} | {high_disease + ' Risk':<15}")
    print("-" * 80)

    for _, row in unique_cities.iterrows():
        city = row['city']
        realtime = get_realtime_data(city)
        
        if realtime:
            source = "LIVE API"
            temp = realtime['temp']
            humidity = realtime['humidity']
            wind = realtime['wind']
            aqi = realtime['aqi']
        else:
            source = "CSV DATA"
            temp = row.get('temperature', 25)
            humidity = row.get('humidity', 50)
            wind = row.get('wind_speed', 10)
            aqi = 50

        # Create Profile
        features = {
            "disease_name": healthy_disease,
            "severity": healthy_severity,
            "city": city,
            "temperature": temp,
            "humidity": humidity,
            "wind_speed": wind,
            "uv_index": row.get('uv_index', 5),
            "aqi": aqi,
            "age": 30,
            "bmi": 22.0,
            "smoking": "No",
            "alcohol": "No",
            "altitude": row.get('altitude', 0)
        }
        
        # Test Healthy
        lvl_h, score_h, _ = predict_risk_level(features)
        
        # Test High Risk
        features_high = features.copy()
        features_high["disease_name"] = high_disease
        features_high["severity"] = high_severity
        lvl_hi, score_hi, _ = predict_risk_level(features_high)
        
        print(f"{city:<15} | {source:<10} | {int(temp):<5} | {lvl_h:<15} ({score_h:.1f}) | {lvl_hi:<15} ({score_hi:.1f})")

if __name__ == "__main__":
    if not API_KEY:
        print("Warning: OPENWEATHER_API_KEY not found in .env. Using CSV data only.")
    else:
        print(f"Using OpenWeather API Key: {API_KEY[:4]}...{API_KEY[-4:]}")
        
    print("Travel Risk Assessment - Real-time vs. CSV Test")
    test_all_destinations()
