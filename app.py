import logging
import os
import re
import requests
import random
import pandas as pd
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, has_request_context, redirect, render_template, request, session, url_for
from pymongo import MongoClient
from bson import ObjectId
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash

from ml_model import predict_risk_level

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent
MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.environ.get("MONGODB_DB", "travel_health_advisory")
client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
db = client[MONGODB_DB]
users_collection = db["users"]
assessments_collection = db["assessments"]

HEALTH_DF = pd.read_csv(BASE_DIR / 'health.csv').fillna('')
TOURIST_DF = pd.read_csv(BASE_DIR / 'tourist_places.csv').fillna('')

DISEASE_DB = {}
for _, row in HEALTH_DF.iterrows():
    disease_name = str(row['disease_name']).strip()
    if not disease_name:
        continue
    DISEASE_DB[disease_name] = {
        'severity': row['severity'],
        'medications': row['medications'],
        'safety_tips': row['safety_tips'],
        'precautions': row['precautions']
    }

DISEASES_LIST = sorted(DISEASE_DB.keys())

TOURIST_DB = {}
for _, row in TOURIST_DF.iterrows():
    city_name = str(row['city']).strip()
    if city_name and city_name not in TOURIST_DB:
        TOURIST_DB[city_name] = {
            'state': row['state'],
            'tourist_place': row['tourist_place'],
            'category': row['category'],
            'climate_type': row['climate_type'],
            'altitude': row.get('altitude', 0)
        }

CITIES_LIST = sorted(TOURIST_DB.keys())

RISK_LEVELS = (
    ("Low", "risk-low", 0, 2),
    ("Moderate", "risk-moderate", 3, 5),
    ("High", "risk-high", 6, 8),
    ("Critical", "risk-critical", 9, 10),
)

app = Flask(__name__, template_folder="templates", static_folder="static")
_secret = os.environ.get("FLASK_SECRET_KEY")
if not _secret:
    raise RuntimeError(
        "FLASK_SECRET_KEY is not set. Add it to your .env file before starting the app."
    )
app.secret_key = _secret
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)
logging.basicConfig(level=logging.INFO)


def clamp(value: int | float, minimum: int | float, maximum: int | float) -> int | float:
    """Clamp a numeric value to a safe range."""
    return max(minimum, min(value, maximum))

def safe_float(value: object, default: float = 0.0) -> float:
    """Coerce any value to float with a safe fallback."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

def normalize_risk_breakdown(raw_breakdown: dict | None, risk_score: float = 0.0) -> dict:
    """Guarantee the template always receives all expected breakdown keys."""
    breakdown = dict(raw_breakdown or {})
    normalized = {
        "medical": round(clamp(safe_float(breakdown.get("medical"), 0.0), 0.0, 10.0), 1),
        "lifestyle": round(clamp(safe_float(breakdown.get("lifestyle"), 0.0), 0.0, 10.0), 1),
        "climate": round(clamp(safe_float(breakdown.get("climate"), 0.0), 0.0, 10.0), 1),
        "environment": round(clamp(safe_float(breakdown.get("environment"), 0.0), 0.0, 10.0), 1),
    }

    if not any(normalized.values()):
        fallback = round(clamp(safe_float(risk_score, 0.0), 0.0, 10.0), 1)
        normalized["medical"] = fallback

    return normalized

def normalize_text(value: str) -> str:
    """Normalize free-text input for matching."""
    return re.sub(r"\s+", " ", (value or "").strip().lower())

def get_user(username: str) -> dict | None:
    return users_collection.find_one({"username": username})

def create_user(username: str, password_hash: str) -> None:
    users_collection.insert_one(
        {
            "username": username,
            "password_hash": password_hash,
            "created_at": datetime.now(timezone.utc),
        }
    )

def update_user_password(username: str, password_hash: str) -> None:
    users_collection.update_one(
        {"username": username},
        {"$set": {"password_hash": password_hash}},
    )

def ensure_demo_user() -> None:
    if not users_collection.count_documents({"username": "demo"}):
        create_user("demo", generate_password_hash("DemoPass123"))

def save_assessment(username: str, form_data: dict, result: dict) -> None:
    assessments_collection.insert_one(
        {
            "username": username,
            "submitted_at": datetime.now(timezone.utc),
            "form_data": form_data,
            "result": result,
        }
    )

def load_user_history(username: str) -> list[dict]:
    records = []
    for doc in assessments_collection.find({"username": username}).sort("submitted_at", -1):
        records.append(
            {
                "submitted_at": doc["submitted_at"].strftime("%Y-%m-%d %H:%M"),
                "destination": doc["form_data"].get("destination", "Unknown"),
                "risk_level": doc.get("result", {}).get("risk_level", "Unknown"),
                "risk_score": doc.get("result", {}).get("risk_score", "N/A"),
                "summary": doc.get("result", {}).get("risk_overview", ""),
                "disease": doc["form_data"].get("disease", "Unknown"),
                "travel_date": doc["form_data"].get("travel_date", "Not provided"),
                "notes": doc["form_data"].get("notes", ""),
                "id": str(doc["_id"]),
            }
        )
    return records

def validate_username(username: str) -> str:
    cleaned = (username or "").strip()
    if len(cleaned) < 3:
        raise ValueError("Username must be at least 3 characters long.")
    if len(cleaned) > 30:
        raise ValueError("Username must be at most 30 characters long.")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", cleaned):
        raise ValueError("Username can only contain letters, numbers, underscores, and hyphens.")
    return cleaned

def validate_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    return password

def parse_form(form) -> dict:
    destination = (form.get("destination", "") or "").strip()
    if not destination:
        raise ValueError("Please enter a destination.")
        
    disease = (form.get("disease", "") or "").strip()
    if not disease:
        raise ValueError("Please select a disease profile.")
        
    if disease not in DISEASES_LIST:
        raise ValueError("Please select a disease from the available list.")

    travel_date = (form.get("travel_date", "") or "").strip()
    if not travel_date:
        raise ValueError("Please select a valid travel date.")

    # Optional but defaulted vitals
    age = form.get("age", "30")
    height = form.get("height", "170")
    weight = form.get("weight", "70")
    bmi = form.get("bmi", "24.2")
    smoking = form.get("smoking", "No")
    alcohol = form.get("alcohol", "No")
    activity = (form.get("activity", "low") or "low").strip().lower()
    if activity not in {"low", "moderate", "high"}:
        activity = "low"

    return {
        "disease": disease,
        "destination": destination,
        "travel_date": travel_date,
        "age": age,
        "height": height,
        "weight": weight,
        "bmi": bmi,
        "smoking": "Yes" if smoking == "Yes" else "No",
        "alcohol": "Yes" if alcohol == "Yes" else "No",
        "activity": activity,
        "notes": form.get("notes", "").strip()
    }

def get_realtime_weather(city: str) -> dict:
    from dotenv import load_dotenv
    load_dotenv(override=True)
    
    fallback = TOURIST_DB.get(city, {})
    api_key = os.environ.get("OPENWEATHER_API_KEY", "")
    if not api_key or api_key == "your-api-key-here":
        print("API FALLBACK: Using fallback weather data (OpenWeather API key missing in .env)")
        return {
            "temperature": fallback.get("temperature", 25),
            "humidity": fallback.get("humidity", 50),
            "wind_speed": fallback.get("wind_speed", 10),
            "uv_index": fallback.get("uv_index", 5.0),
            "aqi": 50,
            "is_realtime": False
        }
    
    try:
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            temp = data['main']['temp']
            humidity = data['main']['humidity']
            wind = data['wind']['speed'] * 3.6
            
            lat = data['coord']['lat']
            lon = data['coord']['lon']
            aqi_url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={api_key}"
            aqi_resp = requests.get(aqi_url, timeout=5)
            aqi_value = 50
            if aqi_resp.status_code == 200:
                aqi_data = aqi_resp.json()
                raw_aqi = aqi_data['list'][0]['main']['aqi']
                aqi_value = raw_aqi * 40
            else:
                 print(f"API FALLBACK: Air pollution API returned {aqi_resp.status_code} for {city}")
            
            return {
                "temperature": round(temp, 1),
                "humidity": round(humidity, 1),
                "wind_speed": round(wind, 1),
                "uv_index": fallback.get("uv_index", 5.0),
                "aqi": int(aqi_value),
                "is_realtime": True
            }
        else:
             print(f"API FALLBACK: Weather API returned {resp.status_code} for {city}. URL: {url}")
    except Exception as e:
        print(f"Failed to fetch Weather for {city}: {e}")
        
    return {
        "temperature": fallback.get("temperature", 25),
        "humidity": fallback.get("humidity", 50),
        "wind_speed": fallback.get("wind_speed", 10),
        "uv_index": fallback.get("uv_index", 5.0),
        "aqi": 50,
        "is_realtime": False
    }

def suggest_alternative_place(original_city: str, disease_severity: str) -> dict | None:
    original_state = TOURIST_DB.get(original_city, {}).get("state", None)
    if not original_state:
        return None
        
    candidates = []
    for city, info in TOURIST_DB.items():
        if city != original_city and info.get('state') == original_state:
            features = {
                "disease_name": "Any", "severity": disease_severity, "city": city,
                "temperature": 25, "humidity": 50,
                "wind_speed": 10, "uv_index": 5.0, "aqi": 50
            }
            risk_level, score, _breakdown = predict_risk_level(features)
            if risk_level in ["Low", "Moderate"]:
                candidates.append({
                    "city": city,
                    "tourist_place": info['tourist_place'],
                    "risk_level": risk_level,
                    "temperature": 25
                })
                
    if candidates:
        # Only suggest alternative if current place is at least Moderate risk
        return random.choice(candidates)
    return None

def dedupe_list(raw_string: str) -> list[str]:
    items = [item.strip() for item in raw_string.split(';') if item.strip()]
    seen = set()
    result = []
    for x in items:
        if x not in seen:
            seen.add(x)
            result.append(x)
    return result

def augment_advisory_tips(safety_tips: list[str], form_data: dict, weather: dict) -> list[str]:
    """Dynamically append real warnings based on real world metrics mapped to health stats"""
    bmi_val = 24.0
    try:
        bmi_val = float(form_data.get("bmi", "24"))
    except:
        pass
    age_val = 30
    try:
        age_val = int(form_data.get("age", "30"))
    except:
        pass
    
    tips = list(safety_tips)
    if bmi_val > 25.0 and weather.get("temperature", 20) > 30:
        tips.append("Heat Exhaustion Warning: Elevated BMI combined with high temperatures increases risk. Stay in shaded areas.")
    if age_val > 60 and weather.get("aqi", 50) > 100:
        tips.append("Respiratory Note: Seniors should limit prolonged outdoor exertion due to current poor air quality (AQI > 100).")
    if form_data.get("smoking") == "Yes":
        tips.append("Avoid smoking prior to high altitude or physically demanding tourist spots.")
        
    return tips

def build_advisory(form_data: dict) -> dict:
    city = form_data["destination"]
    disease = form_data["disease"]
    
    disease_info = DISEASE_DB.get(disease, {'severity': 'Low', 'medications':'Standard First Aid', 'safety_tips':'Stay safe', 'precautions':'Be careful'})
    weather = get_realtime_weather(city)
    
    # Convert form values to proper types
    try:
        age = int(form_data.get("age", 30))
    except (ValueError, TypeError):
        age = 30
        
    try:
        bmi = float(form_data.get("bmi", 22.0))
    except (ValueError, TypeError):
        bmi = 22.0
    
    features = {
        "disease_name": disease,
        "severity": disease_info["severity"].lower(),
        "city": city,
        "temperature": weather["temperature"],
        "humidity": weather["humidity"],
        "wind_speed": weather["wind_speed"],
        "uv_index": 5.0,
        "aqi": weather["aqi"],
        "age": age,
        "bmi": bmi,
        "smoking": form_data.get("smoking", "No"),
        "alcohol": form_data.get("alcohol", "No"),
        "activity": form_data.get("activity", "low"),
        "altitude": TOURIST_DB.get(city, {}).get("altitude", 0.0),
        "climate_type": TOURIST_DB.get(city, {}).get("climate_type", ""),
    }
    
    # API Status Check
    if weather["is_realtime"]:
        print(f"API SUCCESS: Fetched real-time data for {city}")
    else:
        print(f"API FALLBACK: Using historical data for {city} (Check your API Key)")

    risk_level, risk_score, risk_breakdown = predict_risk_level(features)
    risk_breakdown = normalize_risk_breakdown(risk_breakdown, risk_score)
    risk_class = next((css for label, css, _min, _max in RISK_LEVELS if label == risk_level), "risk-critical")
    risk_percent = clamp(risk_score * 10, 10, 100)

    # Dynamic explanation of why this risk level was chosen
    main_environmental_driver = "Temperature"
    if weather["aqi"] > 100: main_environmental_driver = "Air Quality"
    elif weather["humidity"] > 80: main_environmental_driver = "Humidity"
    elif weather["uv_index"] > 8: main_environmental_driver = "UV Exposure"
    
    # Summary logic based on risk and disease
    is_healthy = "none" in disease.lower() or "healthy" in disease.lower()
    
    overview_map = {
        "Low": "Looks like smooth sailing! Your profile is well-suited for this destination.",
        "Moderate": "A mostly safe choice, but keep an eye on environmental changes.",
        "High": "Caution advised. Environmental factors may impact your specific health profile.",
        "Critical": "Strongly consider the alternative destination provided below for your safety."
    }
    
    if is_healthy and risk_level == "Low":
        risk_overview = "Congratulations! You're in great shape for this trip. Enjoy your travels without any major health concerns."
    else:
        risk_overview = overview_map.get(risk_level, "")

    alt_place = None
    if risk_level in ["High", "Critical"]:
        alt_place = suggest_alternative_place(city, disease_info["severity"])

    # Alternative Filtering: Healthy travelers don't need alternatives for Moderate risk
    if is_healthy and risk_level in ["Low", "Moderate"]:
        alt_place = None

    # Possible environment-based risks for ANY traveler at this destination
    potential_threats = []
    
    _temp = weather.get("temperature", 25)
    _hum = weather.get("humidity", 50)
    _aqi = weather.get("aqi", 50)
    _uv = weather.get("uv_index", 5)
    _alt = TOURIST_DB.get(city, {}).get("altitude", 0)

    if _alt > 2500:
        potential_threats.append("Acute Mountain Sickness (AMS) / Hypoxia")
    if _temp > 35:
        potential_threats.append("Severe Dehydration & Heat Stroke")
    elif _temp < 5:
        potential_threats.append("Hypothermia & Frostnip Risk")
    if _hum > 85 and _temp > 25:
        potential_threats.append("Heat Exhaustion / Tropical Illnesses")
    if _aqi > 150:
        potential_threats.append("Critical Respiratory Distress (High Air Pollution)")
    elif _aqi > 100:
        potential_threats.append("Asthma / Allergy Flare-ups")
    if _uv > 8:
        potential_threats.append("Severe UV Radiation Damage / Dermatitis")

    return {
        "destination_name": city,
        "temperature": weather["temperature"],
        "humidity": weather["humidity"],
        "wind_speed": weather["wind_speed"],
        "aqi": weather["aqi"],
        "is_realtime": weather["is_realtime"],
        "disease": disease,
        "severity": disease_info["severity"],
        "risk_level": risk_level,
        "risk_class": risk_class,
        "risk_score": risk_score,
        "risk_breakdown": risk_breakdown,
        "risk_percent": risk_percent,
        "risk_overview": risk_overview,
        "medications": dedupe_list(disease_info["medications"]),
        "safety_tips": augment_advisory_tips(dedupe_list(disease_info["safety_tips"]), form_data, weather),
        "precautions": dedupe_list(disease_info["precautions"]),
        "potential_threats": potential_threats,
        "alt_place": alt_place
    }

def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    return wrapped

@app.context_processor
def inject_helpers():
    def asset_url(filename: str) -> str:
        asset_path = BASE_DIR / "static" / Path(filename)
        version = int(asset_path.stat().st_mtime) if asset_path.exists() else 0
        return url_for("static", filename=filename, v=version)
    return {
        "asset_url": asset_url,
        "current_user": session.get("username") if has_request_context() else None,
    }

def render_assessment(*, error: str | None = None, form_data: dict | None = None):
    return render_template(
        "index.html",
        error=error,
        form_data=form_data or {},
        supported_destinations=CITIES_LIST,
        supported_diseases=DISEASES_LIST,
        current_year=datetime.now().year,
    )

@app.route("/")
def landing():
    if "username" in session:
        return redirect(url_for("assessment"))
    return render_template("landing.html")

@app.route("/help")
def help_page():
    return render_template("help.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    print(f"[LOGIN] Route called with method={request.method}")
    if request.method == "POST":
        username = (request.form.get("username", "") or "").strip()
        password = request.form.get("password", "")
        print(f"[LOGIN] POST received: username='{username}', password_len={len(password)}")
        record = get_user(username)
        print(f"[LOGIN] get_user returned: {type(record)} - {bool(record)}")
        password_hash = record.get("password_hash", "") if isinstance(record, dict) else ""
        print(f"[LOGIN] password_hash exists: {bool(password_hash)}")
        try:
            password_matches = bool(record) and bool(password_hash) and check_password_hash(password_hash, password)
            print(f"[LOGIN] password_matches={password_matches}")
        except ValueError as e:
            print(f"[LOGIN] Exception in password check: {e}")
            password_matches = False
        if password_matches:
            print(f"[LOGIN] Password matched for {username}, setting session")
            session["username"] = username
            print(f"[LOGIN] Session after set: {dict(session)}")
            resp = redirect(url_for("assessment"))
            print(f"[LOGIN] Redirect response Set-Cookie headers: {resp.headers.getlist('Set-Cookie')}")
            return resp
        print(f"[LOGIN] Password did not match or user not found")
        return render_template("login.html", error="Invalid username or password.", username=username)
    return render_template("login.html", error=None, username="")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    username = ""
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        try:
            cleaned_username = validate_username(username)
            validate_password(password)
            if password != confirm_password:
                raise ValueError("Passwords do not match.")
        except ValueError as exc:
            return render_template("signup.html", error=str(exc), success=None, username=username)
        if get_user(cleaned_username):
            return render_template("signup.html", error="That username is already registered.", success=None, username=username)
        create_user(cleaned_username, generate_password_hash(password))
        return render_template("signup.html", error=None, success="Account created successfully. You can sign in now.", username="")
    return render_template("signup.html", error=None, success=None, username="")




@app.route("/top-destinations")
def top_destinations():
    # Extract unique (state, place, city) combinations from the entire dataframe
    unique_places = TOURIST_DF[['state', 'tourist_place', 'city']].drop_duplicates(subset=['tourist_place'])
    
    # Sort for professional presentation
    sorted_places = unique_places.sort_values(by=['state', 'tourist_place'])
    
    places_list = []
    for _, row in sorted_places.iterrows():
        places_list.append({
            "state": row['state'],
            "place": row['tourist_place'],
            "city": row['city']
        })
        
    return render_template("top_destinations.html", places=places_list)

@app.route("/forgot", methods=["GET", "POST"])
def forgot():
    return render_template("forgot.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))

@app.route("/assessment")
@login_required
def assessment():
    city = request.args.get('city')
    form_data = {'destination': city} if city else None
    return render_assessment(form_data=form_data)

@app.route("/home")
@app.route("/dashboard")
@login_required
def dashboard():
    records = load_user_history(session["username"])
    return render_template("dashboard.html", records=records)

@app.route("/history")
@login_required
def history():
    records = load_user_history(session["username"])
    return render_template("history.html", records=records)

@app.route("/result/<record_id>")
@login_required
def view_result(record_id):
    try:
        doc = assessments_collection.find_one({"_id": ObjectId(record_id)})
        if not doc or doc.get("username") != session["username"]:
            return render_template("error.html", title="Not Found", message="This assessment record does not exist or access was denied."), 404
            
        # Compatibility Layer for old records (3-factor structure)
        res = doc["result"]
        bd = dict(res.get("risk_breakdown", {}))
        if "health" in bd and "medical" not in bd:
            bd["medical"] = bd.pop("health")
            bd["lifestyle"] = 0.0
        res["risk_breakdown"] = normalize_risk_breakdown(bd, res.get("risk_score", 0))
            
        return render_template("result.html", form_data=doc["form_data"], result=doc["result"])
    except Exception as e:
        app.logger.error(f"Error retrieving record {record_id}: {e}")
        return render_template("error.html", title="Error", message="Could not retrieve the assessment record."), 500

@app.route("/predict", methods=["POST"])
@login_required
def predict():
    try:
        form_data = parse_form(request.form)
        result = build_advisory(form_data)
        try:
            save_assessment(session["username"], form_data, result)
        except Exception as db_err:
            app.logger.warning(f"Could not save assessment to database: {db_err}")
            # Continue anyway - show the result even if we can't save it
        return render_template("result.html", form_data=form_data, result=result)
    except ValueError as exc:
        app.logger.warning(f"Validation error in /predict: {exc}")
        return render_assessment(error=str(exc), form_data=request.form.to_dict())
    except Exception as exc:
        app.logger.exception(f"Unexpected error in /predict: {exc}")
        error_msg = str(exc) if len(str(exc)) < 200 else "An unexpected error occurred. Please try again."
        return render_template("error.html", title="Server Error", message=error_msg), 500

@app.errorhandler(Exception)
def handle_unexpected_error(error):
    if isinstance(error, HTTPException):
        return error
    app.logger.exception("Unhandled application error: %s", error)
    return render_template("error.html", title="Server Error", message="Something went wrong. Please try again."), 500

if __name__ == "__main__":
    ensure_demo_user()
    debug_mode = os.environ.get("DEBUG", "False").lower() == "true"
    port = int(os.environ.get("PORT", "5051"))
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
