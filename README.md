# Travel Health Advisory

This project is a Flask-based web application for checking travel health risk using a user's health profile and destination details.

## Tech Stack

- Backend: Python + Flask
- Frontend: HTML, CSS, JavaScript
- Styling: Custom CSS
- Client-side behavior: Vanilla JavaScript
- Authentication: MongoDB user collection with password hashing

## Project Structure

```text
cursor ML project/
|-- app.py
|-- ml_model.py
|-- train_model.py
|-- requirements.txt
|-- .env
|-- .env.example
|-- README.md
|-- data/
|   |-- train.csv
|   `-- test.csv
|-- models/
|   `-- travel_risk_model.joblib
|-- static/
|   |-- css/
|   |   `-- style.css
|   `-- js/
|       `-- app.js
`-- templates/
    |-- base.html
    |-- landing.html
    |-- help.html
    |-- login.html
    |-- signup.html
    |-- forgot.html
    |-- index.html
    |-- result.html
    `-- error.html
```

## Features

- Landing page
- Login, signup, and password reset
- Health assessment form
- Destination input
- Travel risk prediction result
- Environmental advisory:
  - Temperature
  - Humidity
  - AQI
  - Common diseases
- Risk level categories:
  - Low
  - Moderate
  - High
  - Critical
- Personalized precautions and recommendations

## System Architecture

- Frontend: login/signup pages, health and travel form, result dashboard
- Backend: Flask server for authentication, input validation, response formatting, and ML orchestration
- Data preprocessing layer: standardization for numeric fields and one-hot encoding for categorical fields
- ML model: trained `RandomForestClassifier` loaded from `models/travel_risk_model.joblib`
- Risk scoring engine: model-based risk prediction plus fallback scoring
- Health advisory engine: tailored guidance based on destination, environment, and user health profile
- Result formatter: structured result object for the dashboard

## How To Run

### 1. Open the project folder

Open PowerShell or terminal inside:

```powershell
C:\Users\sathe\OneDrive\Documents\Mini Project\cursor ML project
```

### 2. Install dependencies

```powershell
pip install -r requirements.txt
```

### 3. Configure MongoDB

Set environment variables in `.env` or your shell before starting the app:

```powershell
$env:MONGODB_URI="mongodb://localhost:27017"
$env:MONGODB_DB="travel_health_advisory"
```

Optionally copy `.env.example` to `.env` and update the values.

### 4. Generate datasets, train the model, and evaluate on test data

```powershell
python train_model.py
```

This script will:
- Generate a synthetic health and destination dataset
- Save `data/train.csv` and `data/test.csv`
- Preprocess numeric features with `StandardScaler` and categorical features with `OneHotEncoder`
- Train a `RandomForestClassifier`
- Evaluate predictions on the test dataset
- Save the trained model to `models/travel_risk_model.joblib`

### 4. Start the Flask app

```powershell
python app.py
```

The app runs by default at:

```text
http://127.0.0.1:5051
```

## How To Stop The Server

Press:

```text
Ctrl + C
```

in the terminal where the Flask server is running.

## Routes Used In This Project

- `/` - Landing page
- `/help` - Help page
- `/login` - Login page
- `/signup` - Signup page
- `/forgot` - Reset password page
- `/assessment` - Main health profile form
- `/home` - Alternate route for assessment
- `/predict` - Result page after form submission
- `/logout` - Logout route

## Main Files

- `app.py` - Main Flask backend and route logic
- `templates/` - All HTML pages
- `static/css/style.css` - Full UI styling
- `static/js/app.js` - Form validation, autosave, and result-page interactions
- MongoDB database - User authentication and assessment storage

## Notes

- This project does not use Streamlit, React, dashboards, ML notebooks, or extra frameworks.
- The app is fully based on Flask, HTML, CSS, and JavaScript only.
- Destination advisory data is currently based on local profiles defined inside `app.py`.

## Optional Settings

You can override the default port:

```powershell
$env:PORT=5000
python app.py
```

You can also enable debug mode:

```powershell
$env:DEBUG='true'
python app.py
```
