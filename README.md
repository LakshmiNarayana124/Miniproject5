# IntelliWatch

**Real-time industrial condition monitoring and anomaly detection.**
Edge sensors on a Raspberry Pi stream vibration, temperature, and current readings over MQTT/HTTP to a FastAPI ML backend. A React dashboard shows live charts, ISO severity classifications, fault signatures, RUL forecasts, and a 3D interactive hardware model.

---

## Live URLs

| Service | URL |
|---|---|
| **Frontend** | https://intelliwatch-iw.vercel.app |
| **Backend API** | https://intelliwatch-backend.onrender.com |
| **API Docs** | https://intelliwatch-backend.onrender.com/docs |
| **Database** | Neon Postgres (serverless, free tier) |

> **Note:** The Render free tier spins down after 15 min of inactivity. The first request after idle takes ~30 s to wake — click any login button and wait a moment. Subsequent requests are instant.

---

## Architecture

```
┌─────────────────────┐     HTTPS/WSS     ┌──────────────────────┐     SQL     ┌──────────────┐
│   Vercel (Frontend) │ ◄────────────────► │  Render (Backend)    │ ◄──────────► │ Neon Postgres│
│   React 19 + Vite   │                   │  FastAPI + Python 3.11│             │ (serverless) │
│   PWA installable   │                   │  ML ensemble, Auth    │             └──────────────┘
└─────────────────────┘                   └──────────────────────┘
                                                    ▲
                                                    │ MQTT / HTTP POST
                                          ┌─────────┴────────┐
                                          │  Raspberry Pi    │
                                          │  ADXL345 (vib)   │
                                          │  DS18B20 (temp)  │
                                          │  ACS712 (current)│
                                          └──────────────────┘
```

**Free-tier cost: $0/month** (Vercel Hobby + Render Free + Neon Free)

---

## What It Does

### Sensor Monitoring
Three sensor channels stream from a Raspberry Pi over MQTT/HTTP:
- **Vibration** — ADXL345 accelerometer, m/s² RMS
- **Temperature** — DS18B20 probe, °C
- **Current** — ACS712 hall-effect sensor + ADS1115 ADC, Amps

Each reading is classified against **ISO 10816-3 / IEC 60034-1** severity zones:
`normal → warning → critical`

### ML Anomaly Detection
Four-model ensemble trained on the **KAIST bearing fault dataset**:
| Model | Role |
|---|---|
| XGBoost | Primary classifier (tabular features) |
| Isolation Forest | Unsupervised outlier detection |
| ONNX Runtime (GRU) | Sequence-pattern anomaly |
| Scikit-learn Pipeline | Feature extraction + scaling |

### Fault Signatures
Seven fault types scored per **ISO 10816-3 / ISO 13373-1**, displayed as confidence chips:
- Bearing wear, imbalance, thermal overload, electrical overload, misalignment, looseness, compound faults

### Remaining Useful Life (RUL)
Least-squares slope on rolling anomaly score projects when the critical threshold will be crossed (**ISO 13381-1**). Banner states: Stable / Warning (<72 h) / Soon (<24 h) / Imminent (<4 h).

### Authentication
- **Username + password** (Argon2 hashing, JWT tokens, 30-min expiry, auto-refresh)
- **Google Sign-In** (Firebase OAuth → backend token exchange)
- **Phone OTP** (Firebase SMS → backend token exchange, requires Firebase Blaze plan)
- **Offline Demo** mode — works with no backend, synthetic sensor data
- Roles: `ADMIN`, `MAINTENANCE_ENGINEER`, `OPERATOR`
- Admin accounts created by invitation token only

### Dashboard Pages
| Route | Page | Access |
|---|---|---|
| `/` | Home — live sensor cards, system overview, ML panel, alert log | All |
| `/vibration` | Vibration sensor detail + history | All |
| `/temperature` | Temperature sensor detail + history | All |
| `/current` | Current sensor detail + history | All |
| `/explorer` | 3D interactive hardware model (Three.js) with ML replay | All |
| `/vision` | Equipment image analysis (Gemini Vision AI) | All |
| `/profile` | User profile, timezone, session info | All |
| `/about` | Project overview, team, tech stack | All |
| `/admin/users` | User management, roles, invitations | ADMIN only |

### Other Features
- **PWA** — installable on Android/iOS ("Add to Home Screen")
- **Multi-language** — 10 languages (EN, TE, HI, ES, FR, DE, JA, KO, ZH, AR)
- **Dark / Light theme** toggle
- **IoT mode** — live hardware data via WebSocket
- **Simulation mode** — local synthetic readings (no hardware needed)
- **Audit export** — CSV + JSON (IEC 62443 compliance)
- **Chatbot** (Dify-powered) — natural language queries about sensor data
- **Leaderboard** — operator feedback scoring

---

## Repository Structure

```
IntelliWatch/
├── Backend/                    # FastAPI application
│   ├── server.py               # Main app, all API routes
│   ├── auth.py                 # JWT auth, Firebase login, roles
│   ├── auth_security_store.py  # Token store, rate limiting
│   ├── database.py             # Postgres/SQLite abstraction layer
│   ├── intelliwatch_brain.py   # ML ensemble orchestration
│   ├── intelliwatch_engine.py  # Anomaly scoring, severity zones
│   ├── feature_extractor.py    # Signal feature extraction
│   ├── learning_system.py      # Online learning, model updates
│   ├── training_pipeline.py    # KAIST dataset training pipeline
│   ├── inference.py            # ONNX + sklearn inference
│   ├── sensor_reader.py        # Raspberry Pi hardware I/O
│   ├── sensor_config.py        # Sensor thresholds (ISO 10816-3)
│   ├── iot_layer.py            # MQTT broker + HTTP IoT ingestion
│   ├── vision_service.py       # Gemini Vision equipment analysis
│   ├── equipment_detection_service.py  # YOLO object detection
│   ├── chatbot_api.py          # Dify chatflow proxy
│   ├── calibration.py          # Sensor calibration API
│   ├── recommendations.py      # Maintenance recommendations
│   ├── iso_standards.py        # ISO 10816-3 / IEC 60034-1 rules
│   ├── obs_service.py          # OBS streaming integration
│   ├── explorer_ml.py          # 3D explorer ML history
│   ├── model_registry.py       # ML model versioning
│   ├── reset_engineer.py       # Engineer account reset utility
│   ├── requirements.txt        # Python dependencies
│   ├── nixpacks.toml           # Render/Railway build config
│   ├── Procfile                # Uvicorn start command
│   ├── runtime.txt             # Python 3.11.9
│   ├── database/
│   │   └── intelliwatch.db     # SQLite (local dev only)
│   └── models/                 # Trained ML model files (.pkl, .onnx)
│
├── frontend/                   # React 19 + Vite SPA
│   ├── src/
│   │   ├── App.jsx             # Root component, routing, auth state
│   │   ├── main.jsx            # Entry point, SW registration
│   │   ├── firebase.js         # Firebase app + auth init
│   │   ├── apiConfig.js        # API base URL + WS URL helpers
│   │   ├── sensors.js          # Sensor definitions, thresholds, colors
│   │   ├── i18n.js             # Multi-language translations (10 langs)
│   │   ├── useSensorData.js    # WebSocket + polling sensor hook
│   │   ├── useTokenRefresh.js  # JWT auto-refresh hook
│   │   ├── useLang.js          # Language preference hook
│   │   ├── useRUL.js           # RUL computation hook
│   │   ├── mlEngine.js         # Client-side ML feature extraction
│   │   ├── faultSignatures.js  # Fault pattern definitions
│   │   ├── activityLog.js      # Session activity tracking
│   │   └── components/
│   │       ├── LoginPage.jsx   # Login (password + Google + Phone OTP)
│   │       ├── Navbar.jsx      # Top nav, mode selector, language
│   │       ├── SensorPage.jsx  # Individual sensor detail page
│   │       ├── SensorExplorer.jsx  # 3D Three.js hardware model
│   │       ├── AlertLog.jsx    # Alert history + operator feedback
│   │       ├── MLStatusPanel.jsx   # ML model status + fault chips
│   │       ├── ControlSignalBanner.jsx  # Live control signals
│   │       ├── ExplorerHistory.jsx      # ML history replay
│   │       ├── TenderLeaderboard.jsx    # Operator leaderboard
│   │       ├── Chatbot.jsx     # Dify chatbot widget
│   │       ├── VisionEquipment.jsx  # Gemini Vision analysis
│   │       ├── ProfilePage.jsx # User profile + settings
│   │       ├── UserManagement.jsx  # Admin user management
│   │       └── AboutPage.jsx   # Project info
│   ├── public/
│   │   ├── sw.js               # PWA service worker (network-first HTML)
│   │   ├── manifest.json       # PWA manifest
│   │   └── icons/              # App icons (192px, 512px)
│   ├── index.html              # HTML entry point
│   ├── vite.config.js          # Vite + dev proxy config
│   ├── package.json
│   └── vercel.json             # Vercel SPA routing + cache headers
│
├── render.yaml                 # Render backend deploy config
├── vercel.json                 # Vercel frontend deploy config (root)
├── DEPLOYMENT.md               # Full deployment guide
├── KAIST/                      # Raw bearing fault dataset (not committed)
└── docs/                       # Additional documentation
```

---

## Deployment (Live — $0/month)

### Services Used
| Service | Tier | Purpose |
|---|---|---|
| **Vercel** | Hobby (free) | Frontend hosting + CDN |
| **Render** | Free Web Service | Backend FastAPI server |
| **Neon** | Free (0.5 GB) | Postgres database |
| **Firebase** | Spark (free) | Google Sign-In auth |

### Environment Variables

**Render (Backend):**
```
INTELLIWATCH_SECRET_KEY    = <64-char hex — auto-generated by Render>
DATABASE_URL               = postgresql://...@ep-xxx.neon.tech/neondb?sslmode=require
INTELLIWATCH_CORS_ORIGINS  = https://intelliwatch-iw.vercel.app
FIREBASE_PROJECT_ID        = intelliwatch-66ad0
```

**Vercel (Frontend):**
```
VITE_API_URL                      = https://intelliwatch-backend.onrender.com
VITE_FIREBASE_API_KEY             = AIzaSyDS_tlmIpoPG-4YeB62RjbPf5BT6x-qu0I
VITE_FIREBASE_AUTH_DOMAIN         = intelliwatch-66ad0.firebaseapp.com
VITE_FIREBASE_PROJECT_ID          = intelliwatch-66ad0
VITE_FIREBASE_STORAGE_BUCKET      = intelliwatch-66ad0.firebasestorage.app
VITE_FIREBASE_MESSAGING_SENDER_ID = 174724193863
VITE_FIREBASE_APP_ID              = 1:174724193863:web:e09ddbd891e2cc547d5b62
```

### Re-deploy Steps
1. Push to `main` branch on GitHub — Vercel and Render both auto-deploy.
2. No CLI needed after initial setup.

---

## Running Locally on Windows (Minimum Setup)

**Requirements:** Python 3.11+, Node.js 18+

### Step 1 — Clone

```powershell
git clone https://github.com/LakshmiNarayana124/IntelliWatch-Private.git
cd IntelliWatch-Private
```

### Step 2 — Backend

Open **Terminal 1:**

```powershell
cd Backend

# Create a virtual environment (recommended)
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Set required environment variable
$env:INTELLIWATCH_SECRET_KEY = "dev-secret-key-change-in-production-minimum-32chars"

# Optional: use Neon Postgres instead of local SQLite
# $env:DATABASE_URL = "postgresql://user:pass@ep-xxx.neon.tech/neondb?sslmode=require"

# Start the backend
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

Backend is live at: **http://localhost:8000**
Interactive API docs: **http://localhost:8000/docs**

### Step 3 — Frontend

Open **Terminal 2:**

```powershell
cd frontend

# Install dependencies (first time only)
npm install

# Create local environment file
copy .env.example .env.local
# Edit .env.local and set:
#   VITE_API_URL=http://localhost:8000
#   VITE_FIREBASE_API_KEY=AIzaSyDS_tlmIpoPG-4YeB62RjbPf5BT6x-qu0I
#   (all other VITE_FIREBASE_* values as in .env.example)

# Start the dev server
npm run dev
```

Frontend is live at: **http://localhost:5173**

### Step 4 — Log In

| Method | How |
|---|---|
| **Offline Demo** | Click "Offline Demo" on the login page — no backend needed |
| **Username/password** | Register at `/auth/register` or use seeded admin credentials |
| **Google Sign-In** | Requires Firebase configured + internet access |
| **Phone OTP** | Requires Firebase Blaze plan (SMS billing) |

### Step 5 — Optional: Local HTTPS

If you need HTTPS locally (required for Phone OTP reCAPTCHA):

```powershell
# Install mkcert
winget install FiloSottile.mkcert
mkcert -install
mkcert -cert-file certs\intelliwatch-local.crt -key-file certs\intelliwatch-local.key localhost 127.0.0.1

# Start frontend with HTTPS
cd frontend
npm run dev:https
```

---

## Hardware Setup (Raspberry Pi)

**Wiring:**

| Sensor | Interface | GPIO/Pin |
|---|---|---|
| ADXL345 (vibration) | I2C | SDA=GPIO2, SCL=GPIO3 |
| DS18B20 (temperature) | 1-Wire | GPIO4 |
| ACS712+ADS1115 (current) | I2C | SDA=GPIO2, SCL=GPIO3 (addr 0x48) |

**On the Pi:**

```bash
pip install -r Backend/requirements.txt
export INTELLIWATCH_SECRET_KEY="your-secret-key"
export DATABASE_URL="postgresql://..."  # Neon connection string
uvicorn Backend.server:app --host 0.0.0.0 --port 8000
```

Then connect the React frontend to the Pi's IP:
```
VITE_API_URL=http://192.168.x.x:8000
```

---

## API Reference

Full interactive docs available at `/docs` (Swagger UI) and `/redoc`.

**Key endpoints:**

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/auth/registration-status` | Backend availability probe |
| `POST` | `/auth/login` | Username + password login |
| `POST` | `/auth/firebase-login` | Google / Phone OTP login |
| `POST` | `/auth/register` | Register new user |
| `POST` | `/auth/register-admin` | Register admin (invite token required) |
| `POST` | `/auth/refresh` | Refresh JWT token |
| `WS` | `/stream/sensors` | Live sensor WebSocket stream |
| `WS` | `/stream/status` | Live system status stream |
| `POST` | `/iot/ingest` | IoT device sensor data ingestion |
| `GET` | `/models/status` | ML model status |
| `GET` | `/models/predictions` | Latest ML predictions |
| `POST` | `/learning/feedback` | Submit operator feedback |
| `GET` | `/explorer/history` | 3D explorer ML history |
| `POST` | `/vision/analyse` | Equipment image analysis (Gemini) |
| `POST` | `/vision/detect` | Object detection (YOLO) |
| `GET` | `/leaderboard` | Operator feedback leaderboard |
| `GET` | `/audit/export` | Audit log export (CSV/JSON) |

---

## Tech Stack

**Frontend**
- React 19, Vite 8, React Router 7
- Recharts (sensor charts), Three.js + @react-three/fiber (3D explorer)
- Firebase JS SDK v13 (auth)
- CSS custom properties (dark/light theme)
- PWA — service worker, Web App Manifest

**Backend**
- FastAPI 0.115, Uvicorn, Pydantic v2
- scikit-learn 1.6, XGBoost 2.1, ONNX Runtime 1.31
- Argon2-cffi (password hashing), PyJWT, python-jose
- psycopg2-binary (Postgres), SQLite (local fallback)
- Paho MQTT (IoT broker connectivity)
- Google GenAI SDK (Gemini Vision)
- Pillow, httpx, python-multipart

**Infrastructure**
- Vercel (frontend CDN + serverless), Render (backend container)
- Neon (serverless Postgres), Firebase (identity)
- GitHub Actions (future CI/CD)

---

## Project Background

IntelliWatch was developed as a final-year mini-project to demonstrate:
1. End-to-end IoT pipeline from physical sensors to cloud dashboard
2. ML-based predictive maintenance (anomaly detection + RUL forecasting)
3. Industrial standards compliance (ISO 10816-3, ISO 13373-1, ISO 13381-1, IEC 60034-1, IEC 62443)
4. Production-ready full-stack deployment at zero cloud cost

The KAIST bearing fault dataset was used to train the ML ensemble. The dataset covers normal operation and six bearing fault types under varying load conditions.

---

## License

MIT — see [LICENSE](LICENSE) for details.
