
INTELLIWATCH - PC START GUIDE
=============================

IntelliWatch is a full-stack real-time industrial anomaly-detection and
decision-support system with a React frontend and a FastAPI backend.

REQUIREMENTS
- Windows PC with Python 3.10+ installed
- Node.js 18+ (for the React frontend)
- Internet connection for first-time package installation

START — BACKEND
1. Extract the ZIP to a normal folder.
2. Install Python from https://www.python.org/downloads/ if needed.
   During installation, enable "Add Python to PATH".
3. Double-click RUN_ON_WINDOWS.bat  —  OR  —  open a terminal and run:
     cd Backend
     pip install -r requirements.txt
     uvicorn server:app --reload --host 0.0.0.0 --port 8000
4. Interactive API docs:  http://127.0.0.1:8000/docs

START — FRONTEND
1. Open a second terminal:
     cd frontend
     npm install
     npm run dev
2. Open the URL shown (default: http://localhost:5173)

NOTES
- Sensors run in SIMULATION_MODE by default (synthetic data).
  Real hardware (ADXL345, DS18B20, ACS712+ADS1115) requires a
  Raspberry Pi and sensor wiring; see Backend/sensor_config.py.
- Default admin credentials are set via the Backend/.env file
  (copy .env.example to .env and edit before first run).
- To stop any server, press Ctrl+C in its terminal window.

ARCHITECTURE
  frontend/   — React 19 + Vite SPA (dashboard, 3D explorer, chatbot)
  Backend/    — FastAPI + SQLite (sensors, ML, auth, IoT, calibration)
  KAIST/      — Training dataset for the anomaly-detection model

