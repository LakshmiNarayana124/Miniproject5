# IntelliWatch

Real-time industrial condition monitoring and anomaly detection. Edge sensors on a Raspberry Pi stream vibration, temperature, and current readings to a FastAPI ML backend. A React dashboard shows live charts, ISO severity classifications, fault signatures, RUL forecasts, and a 3D interactive hardware model.

---

## Live URLs

| Service | URL |
|---|---|
| **Frontend** | https://intelliwatch-iw.vercel.app |
| **Backend API** | https://intelliwatch-backend.onrender.com |
| **API Docs** | https://intelliwatch-backend.onrender.com/docs |
| **Database** | Neon Postgres (serverless, free) |

> Render free tier sleeps after 15 min idle. First request after sleep takes ~30 s — just wait and retry.

---

## Architecture

```
Browser
  └── React 19 + Vite SPA  (Vercel CDN)
         │ HTTPS / WSS
         └── FastAPI + Python 3.11  (Render free)
                │ SQL
                └── Neon Postgres  (serverless free)

Firebase  →  Google Sign-In (free Spark plan)

Raspberry Pi  (optional hardware)
  └── ADXL345 · DS18B20 · ACS712
         │ MQTT / HTTP POST
         └── /iot/ingest
```

**Cost: $0/month** — Vercel Hobby + Render Free + Neon Free + Firebase Spark

---

## Features

### Sensor Monitoring
Three channels stream from a Raspberry Pi:
- **Vibration** — ADXL345 accelerometer (m/s² RMS)
- **Temperature** — DS18B20 probe (°C)
- **Current** — ACS712 + ADS1115 ADC (Amps)

Each reading is classified against **ISO 10816-3 / IEC 60034-1** severity zones: `normal → warning → critical`

### ML Anomaly Detection
Four-model ensemble trained on the **KAIST bearing fault dataset**:

| Model | Role |
|---|---|
| XGBoost | Primary tabular classifier |
| Isolation Forest | Unsupervised outlier detection |
| ONNX GRU | Sequence-pattern anomaly |
| Scikit-learn Pipeline | Feature extraction + scaling |

### Fault Signatures
Seven fault types scored per ISO 10816-3 / ISO 13373-1: bearing wear, imbalance, thermal overload, electrical overload, misalignment, looseness, compound faults.

### RUL Forecast
Least-squares slope on rolling anomaly score projects time to critical threshold (ISO 13381-1). States: Stable / Warning <72 h / Soon <24 h / Imminent <4 h.

### Authentication
- Username + password (Argon2, JWT, 30-min expiry, auto-refresh)
- Google Sign-In (Firebase OAuth → backend token exchange)
- Phone OTP (Firebase SMS — requires Blaze plan)
- Offline Demo mode (no backend, synthetic data)
- Roles: `ADMIN`, `MAINTENANCE_ENGINEER`, `OPERATOR`

### Pages

| Route | Page |
|---|---|
| `/` | Home — sensor cards, system overview, ML panel, alert log |
| `/vibration` `/temperature` `/current` | Individual sensor detail + history |
| `/explorer` | 3D interactive hardware model (Three.js) |
| `/vision` | Equipment image analysis (Gemini Vision AI) |
| `/profile` | User profile and settings |
| `/about` | Project overview |
| `/admin/users` | User management (ADMIN only) |

### Other
- PWA — installable on Android/iOS
- 10 languages (EN, TE, HI, ES, FR, DE, JA, KO, ZH, AR)
- Dark / Light theme
- IoT mode (live hardware) and Simulation mode (synthetic)
- Audit export CSV + JSON (IEC 62443)
- Dify-powered chatbot
- Operator feedback leaderboard

---

## Repository Structure

```
IntelliWatch/
├── Backend/
│   ├── server.py                  # FastAPI app, all routes
│   ├── auth.py                    # JWT, Firebase login, roles
│   ├── database.py                # Postgres/SQLite layer
│   ├── intelliwatch_brain.py      # ML ensemble orchestration
│   ├── intelliwatch_engine.py     # Anomaly scoring, ISO zones
│   ├── feature_extractor.py       # Signal feature extraction
│   ├── sensor_reader.py           # Raspberry Pi hardware I/O
│   ├── sensor_config.py           # ISO 10816-3 thresholds
│   ├── iot_layer.py               # MQTT + HTTP IoT ingestion
│   ├── vision_service.py          # Gemini Vision
│   ├── equipment_detection_service.py  # YOLO detection
│   ├── chatbot_api.py             # Dify proxy
│   ├── requirements.txt
│   ├── nixpacks.toml              # Build config
│   ├── Procfile
│   └── runtime.txt                # Python 3.11.9
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx                # Root, routing, auth state
│   │   ├── firebase.js            # Firebase init
│   │   ├── apiConfig.js           # API + WS URL helpers
│   │   ├── sensors.js             # Sensor definitions
│   │   ├── i18n.js                # 10-language translations
│   │   ├── useSensorData.js       # WebSocket + polling hook
│   │   ├── useTokenRefresh.js     # JWT auto-refresh
│   │   └── components/
│   │       ├── LoginPage.jsx      # Login (password/Google/OTP)
│   │       ├── Navbar.jsx
│   │       ├── SensorPage.jsx
│   │       ├── SensorExplorer.jsx # 3D Three.js model
│   │       ├── VisionEquipment.jsx
│   │       ├── ProfilePage.jsx
│   │       ├── UserManagement.jsx
│   │       └── ...
│   ├── public/
│   │   ├── sw.js                  # PWA service worker
│   │   └── manifest.json
│   ├── vite.config.js
│   └── package.json
│
├── render.yaml                    # Render deploy config
├── deploy_render.ps1              # Render deploy script (secrets via env)
├── vercel.json                    # Vercel SPA routing + cache headers
├── DEPLOYMENT.md                  # Full deployment reference
└── README.md
```

---

## Running Locally

**Requirements:** Python 3.11, Node.js 22, Git

### Backend (Terminal 1)

```powershell
cd Backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create `Backend\.env`:
```
INTELLIWATCH_SECRET_KEY=<run: python -c "import secrets; print(secrets.token_hex(32))">
DATABASE_URL=postgresql://...your-neon-url...
INTELLIWATCH_CORS_ORIGINS=http://localhost:5173
FIREBASE_PROJECT_ID=intelliwatch-66ad0
```

```powershell
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
# API docs: http://localhost:8000/docs
```

### Frontend (Terminal 2)

```powershell
cd frontend
npm install
```

Create `frontend\.env.local`:
```
VITE_API_URL=http://localhost:8000
VITE_FIREBASE_API_KEY=AIzaSyDS_tlmIpoPG-4YeB62RjbPf5BT6x-qu0I
VITE_FIREBASE_AUTH_DOMAIN=intelliwatch-66ad0.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=intelliwatch-66ad0
VITE_FIREBASE_STORAGE_BUCKET=intelliwatch-66ad0.firebasestorage.app
VITE_FIREBASE_MESSAGING_SENDER_ID=174724193863
VITE_FIREBASE_APP_ID=1:174724193863:web:e09ddbd891e2cc547d5b62
```

```powershell
npm run dev
# Open: http://localhost:5173
```

### Login Options

| Method | How |
|---|---|
| Offline Demo | Click "Offline Demo" — no backend needed |
| Google Sign-In | Click Google button — requires internet |
| Username/Password | Register at `/docs` → `POST /auth/register` |
| Phone OTP | Requires Firebase Blaze SMS plan |

---

## Deployment

### Services

| Service | Tier | Purpose |
|---|---|---|
| Vercel | Hobby (free) | Frontend CDN |
| Render | Free Web Service | Backend FastAPI |
| Neon | Free (0.5 GB) | Postgres database |
| Firebase | Spark (free) | Google Sign-In |

### Environment Variables

**Render (Backend):**
```
INTELLIWATCH_SECRET_KEY    — 64-char hex string
DATABASE_URL               — Neon connection string
INTELLIWATCH_CORS_ORIGINS  — https://intelliwatch-iw.vercel.app
FIREBASE_PROJECT_ID        — intelliwatch-66ad0
```

**Vercel (Frontend):**
```
VITE_API_URL                       — Render backend URL
VITE_FIREBASE_API_KEY              — from Firebase Console
VITE_FIREBASE_AUTH_DOMAIN          — intelliwatch-66ad0.firebaseapp.com
VITE_FIREBASE_PROJECT_ID           — intelliwatch-66ad0
VITE_FIREBASE_STORAGE_BUCKET       — intelliwatch-66ad0.firebasestorage.app
VITE_FIREBASE_MESSAGING_SENDER_ID  — 174724193863
VITE_FIREBASE_APP_ID               — 1:174724193863:web:e09ddbd891e2cc547d5b62
```

### Auto-deploy
Push to `main` → Vercel and Render both redeploy automatically.

---

## API Reference

Full docs at `/docs` (Swagger) and `/redoc`.

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/auth/registration-status` | Backend probe |
| POST | `/auth/login` | Username + password |
| POST | `/auth/firebase-login` | Google / Phone OTP |
| POST | `/auth/register` | Register user |
| POST | `/auth/refresh` | Refresh JWT |
| WS | `/stream/sensors` | Live sensor stream |
| WS | `/stream/status` | Live system status |
| POST | `/iot/ingest` | IoT device ingestion |
| GET | `/models/status` | ML model status |
| POST | `/learning/feedback` | Operator feedback |
| POST | `/vision/analyse` | Gemini image analysis |
| GET | `/audit/export` | Audit log CSV/JSON |

---

## Tech Stack

**Frontend:** React 19, Vite 8, React Router 7, Recharts, Three.js, Firebase JS SDK v13, PWA

**Backend:** FastAPI 0.115, Uvicorn, Pydantic v2, scikit-learn 1.6, XGBoost 2.1, ONNX Runtime 1.31, Argon2-cffi, PyJWT, psycopg2-binary, Paho MQTT, Google GenAI (Gemini)

**Infrastructure:** Vercel, Render, Neon, Firebase, GitHub

---

## Background

Built as a final-year mini-project demonstrating end-to-end IoT pipeline from physical sensors to cloud dashboard, ML-based predictive maintenance, and industrial standards compliance (ISO 10816-3, ISO 13373-1, ISO 13381-1, IEC 60034-1, IEC 62443) — deployed at zero cloud cost.

KAIST bearing fault dataset used for ML training, covering normal operation and six bearing fault types under varying load conditions.

---

## License

MIT
