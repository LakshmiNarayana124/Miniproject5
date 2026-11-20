# IntelliWatch

**Real-Time Industrial Condition Monitoring & Anomaly Detection**

A full-stack predictive maintenance platform combining live IoT sensor data, ML-based anomaly detection, Firebase authentication, and a PWA-ready React frontend.

---

## Live URLs

| Service | URL |
|---|---|
| **Frontend** (Vercel) | https://intelliwatch.vercel.app |
| **Backend API** (Railway) | https://intelliwatch-backend.up.railway.app |
| **API Docs** | https://intelliwatch-backend.up.railway.app/docs |
| **Database** | Neon Postgres (serverless) |

---

## What It Does

IntelliWatch monitors industrial equipment in real time using three sensor channels — vibration (ADXL345), temperature (DS18B20), and current (ACS712) — running on a Raspberry Pi edge device. Readings stream to a FastAPI backend that runs ensemble ML inference (XGBoost + LightGBM + Isolation Forest + LSTM/GRU) and returns anomaly status, ISO severity zone, fault signature, and a remaining useful life estimate to the React dashboard.

### Core Capabilities

**Monitoring**
- Live sensor dashboard — Vibration, Temperature, Current with real-time area charts
- Anomaly detection with ISO 10816-3 / IEC 60034-1 severity zones
- Fault Signature Library — 7-fault catalogue (Bearing Wear, Mechanical Imbalance, Thermal Overload, Electrical Overload, Shaft Misalignment, Mechanical Looseness, Compound Fault) with confidence scoring per ISO 10816-3 / ISO 13373-1
- Remaining Useful Life (RUL) estimate — ISO 13381-1 prognostics, least-squares trend projection with maintenance window banner
- Alert log with per-sensor history, operator feedback (confirm / dismiss), and IEC 62443 / ISO 55000 audit-trail export (CSV + JSON)
- 3D Sensor Explorer — interactive hardware component viewer with ML classification and history replay

**ML / AI**
- Trained on KAIST bearing fault dataset
- Tabular (XGBoost / LightGBM), Unsupervised (Isolation Forest), Sequence (LSTM/GRU), Ensemble models
- Adaptive learning — operator labels retrain the model automatically
- Model observability — accuracy trend tracking, degradation alerts, sparkline history
- Frontend adaptive ML engine — per-source (hardware / simulation / demo) rolling-window EMA with feedback learning

**Authentication**
- Username + Password (Argon2 hashed, JWT sessions)
- Google Sign-In via Firebase (public-key verification, no service account needed)
- Phone + OTP via Firebase (Blaze plan required for SMS)
- Offline Demo mode — no credentials required, full simulation
- Timezone selector (19 zones), Profile page, Change Password

**IoT**
- MQTT and HTTP device adapters
- Device registration, heartbeat, disconnect/reconnect handling
- Control signal queue (SHUTDOWN / DE_RATE / RUN)
- LCD + relay actuator integration

**Equipment Vision**
- Gemini AI image analysis — upload or capture equipment photo, get component identification and monitoring recommendations
- Live object detection with bounding boxes

**Multilingual AI Assistant**
- Dify Chatflow integration for authenticated sessions
- Offline local knowledge base for Demo mode
- English, Hindi, Kannada, Tamil, Telugu
- Voice input (Web Speech API) and TTS output

**TenderWatch Leaderboard**
- Live industry benchmark table — 7 Indian industrial organisations ranked by Health Score (ISO 55000), Uptime % (ISO 22400-2), MTBF (ISO 14224), Anomaly Response latency
- Backend live data with local simulation fallback

**PWA**
- Service worker with app-shell caching and offline fallback
- Installable via Add to Home Screen on Android (Chrome) and iOS (Safari)

---

## Architecture

```
┌──────────────────┐    HTTPS     ┌──────────────────┐    SSL      ┌──────────────┐
│   Vercel         │◀────────────▶│   Railway        │◀───────────▶│    Neon      │
│  React + Vite    │   REST/WS    │  FastAPI/Uvicorn  │  psycopg2   │  Postgres    │
│  PWA             │              │  ML Ensemble      │             │  Serverless  │
└──────────────────┘              └──────────────────┘             └──────────────┘
         ▲                                  ▲
         │                                  │
         │ Firebase Auth                    │ MQTT / HTTP
         ▼                                  ▼
┌──────────────────┐              ┌──────────────────┐
│  Firebase        │              │  Raspberry Pi    │
│  Google + Phone  │              │  IoT Edge Device │
│  OTP             │              │  ADXL345 / DS18B20│
└──────────────────┘              │  ACS712           │
                                  └──────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, Recharts, React Three Fiber / Drei, React Router |
| Backend | FastAPI, Uvicorn, Pydantic, Python 3.11 |
| ML | XGBoost, LightGBM, scikit-learn, ONNX Runtime, NumPy, pandas |
| Auth | JWT (python-jose), Argon2, Firebase Admin |
| Database | SQLite (local dev) → Neon Postgres (production) |
| IoT | paho-mqtt, httpx |
| Vision AI | Google Gemini (google-genai) |
| Chatbot | Dify Chatflow |
| Deployment | Vercel (frontend), Railway (backend), Neon (database) |
| PWA | Service Worker, Web App Manifest |

---

## Dataset

**KAIST Bearing Fault Dataset** — accelerometer recordings from rotating machinery under normal, inner-race fault, outer-race fault, and ball-fault conditions. Used to train the tabular, unsupervised, and sequence models.

References:
- ISO 10816-3:2009 — Vibration severity zones for industrial machines
- IEC 60034-1 — Motor winding insulation temperature classes
- IEC 60947-4-1 / NEMA MG-1 — Motor overcurrent protection
- ISO 13373-1 — Condition monitoring, vibration measurement
- ISO 13381-1 — Prognostics, remaining useful life
- ISO 55000 — Asset management
- ISO 22400-2 — OEE KPIs
- ISO 14224 — MTBF / reliability data
- IEC 62443 — Industrial cybersecurity (audit trail)

---

## Quick Start (Local — HTTPS)

### Prerequisites
- Python 3.11+, pip
- Node.js 18+, npm
- [mkcert](https://github.com/FiloSottile/mkcert) (for trusted local HTTPS)

### 1. Clone
```bash
git clone https://github.com/LakshmiNarayana124/Miniproject5.git
cd Miniproject5
```

### 2. Generate trusted local certificates
```bash
mkcert -install
cd certs
mkcert -cert-file intelliwatch-local.crt -key-file intelliwatch-local.key localhost 127.0.0.1
cd ..
```

### 3. Backend (HTTPS on port 8000)
```bash
cd Backend
pip install -r requirements.txt
set INTELLIWATCH_SECRET_KEY=<64-char-hex>
set INTELLIWATCH_CORS_ORIGINS=https://localhost:5173
uvicorn server:app --host 0.0.0.0 --port 8000 --reload ^
  --ssl-certfile ../certs/intelliwatch-local.crt ^
  --ssl-keyfile ../certs/intelliwatch-local.key
```

### 4. Frontend (HTTPS on port 5173)
```bash
cd frontend
npm install
npm run dev
```

Vite picks up `certs/intelliwatch-local.crt` automatically. Open **https://localhost:5173**.

---

## Account Registration

Three account types are available when the backend is reachable:

| Role | Access |
|---|---|
| **Operator** | Real-time monitoring, anomaly dashboards, alert log, ML feedback |
| **Maintenance Engineer** | All Operator access + equipment control commands, calibration, maintenance dispatch |
| **Administrator** | Full system access — requires invitation token from existing admin |

Registration buttons appear on the login page when the backend is online. Use **Enter Offline Demo** at any time for a no-credentials simulation session.

---

## Environment Variables

### Backend (`Backend/.env`)

| Variable | Required | Description |
|---|---|---|
| `INTELLIWATCH_SECRET_KEY` | ✅ | 64-char hex string for JWT signing |
| `DATABASE_URL` | Production | Neon Postgres connection string |
| `INTELLIWATCH_CORS_ORIGINS` | ✅ | Comma-separated allowed frontend origins |
| `FIREBASE_PROJECT_ID` | Firebase auth | Firebase project ID |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | Phone OTP | Service account JSON |

### Frontend (`frontend/.env.local`)

| Variable | Required | Description |
|---|---|---|
| `VITE_API_URL` | ✅ | Backend URL (`/` for same-origin via Vite proxy) |
| `VITE_FIREBASE_API_KEY` | Firebase | Firebase web config |
| `VITE_FIREBASE_AUTH_DOMAIN` | Firebase | Firebase web config |
| `VITE_FIREBASE_PROJECT_ID` | Firebase | Firebase project ID |
| `VITE_FIREBASE_MESSAGING_SENDER_ID` | Firebase | Firebase web config |
| `VITE_FIREBASE_APP_ID` | Firebase | Firebase web config |

---

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for the full Neon → Railway → Vercel setup guide.

**Quick links:**
- [Neon](https://neon.tech) — create project, copy connection string → `DATABASE_URL` in Railway
- [Railway](https://railway.app) — New Project → GitHub → `Miniproject5`, Root Directory: `Backend`
- [Vercel](https://vercel.com) — New Project → GitHub → `Miniproject5`, reads root `vercel.json`
- [Firebase Console](https://console.firebase.google.com) → Authentication → enable Google + Phone → add Vercel URL to Authorized Domains

---

## Project Structure

```
Miniproject5/
├── Backend/                  # FastAPI backend (Railway)
│   ├── server.py             # Main app — routes, IoT, streaming
│   ├── auth.py               # JWT + Firebase + registration
│   ├── database.py           # SQLite / Neon Postgres adapter
│   ├── inference.py          # ML inference + fault signature
│   ├── training_pipeline.py  # KAIST model training
│   ├── learning_system.py    # Adaptive retraining
│   ├── obs_service.py        # Model observability
│   ├── iot_layer.py          # MQTT / HTTP IoT adapters
│   ├── vision_service.py     # Gemini image analysis
│   ├── requirements.txt
│   ├── nixpacks.toml         # Railway build config
│   └── Procfile
├── frontend/                 # React + Vite (Vercel)
│   ├── src/
│   │   ├── App.jsx
│   │   ├── faultSignatures.js   # 7-fault ISO rule engine
│   │   ├── useRUL.js            # ISO 13381-1 RUL hook
│   │   ├── mlEngine.js          # Adaptive frontend ML
│   │   ├── sensors.js           # ISO threshold config
│   │   └── components/
│   │       ├── SensorPage.jsx   # Live charts + RUL banner
│   │       ├── MLStatusPanel.jsx # ML state + fault hints
│   │       ├── AlertLog.jsx     # Alerts + export
│   │       ├── LoginPage.jsx    # Auth + registration
│   │       ├── TenderLeaderboard.jsx
│   │       ├── VisionEquipment.jsx
│   │       └── ...
│   └── public/
│       ├── manifest.json        # PWA manifest
│       └── sw.js                # Service worker
├── railway.toml              # Railway deployment config
├── vercel.json               # Vercel SPA config + cache headers
├── DEPLOYMENT.md             # Full deployment guide
└── certs/                    # Local HTTPS certificates (gitignored)
```

---

## Recent Updates

- **Fault Signature Library** — 7-fault catalogue with ISO/IEC rule scoring, shown as confidence chips in ML Status Panel and stored in backend `DetectionTrace.fault_hint`
- **RUL / Maintenance Window** — ISO 13381-1 least-squares trend projection, coloured banner on sensor pages (imminent / soon / warning / stable)
- **Audit-trail Export** — one-click CSV + JSON export from Alert Log, IEC 62443 / ISO 55000 compliant field set
- **Firebase Authentication** — Google Sign-In + Phone OTP with public-key verification
- **PWA** — installable on Android and iOS
- **Deployment** — switched from Render to Railway; Neon Postgres replaces SQLite in production
