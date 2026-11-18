# IntelliWatch

**Real-Time Industrial Condition Monitoring & Anomaly Detection**

A full-stack predictive maintenance platform combining live IoT sensor data, ML-based anomaly detection, Firebase authentication, and a PWA-ready React frontend.

---

## Features

### Authentication
- **Username + Password** login (Argon2 hashed, JWT sessions)
- **Google Sign-In** via Firebase (no backend service account needed — uses Google's public keys)
- **Phone + OTP** via Firebase (requires Firebase Blaze plan for SMS)
- **Demo mode** — offline simulation, no credentials required
- **Timezone selector** on login (default: India IST, 19 zones available)
- **Profile page** — view account details, session info, change password, sign out

### Monitoring
- Live sensor dashboard — Vibration, Temperature, Current
- Real-time anomaly detection with ISO 10816/20816 severity zones
- WebSocket/SSE status streaming
- Alert log with per-sensor history
- 3D Sensor Explorer with ML classification and history replay
- Equipment Vision (Gemini AI image analysis)

### ML / AI
- Trained on KAIST bearing fault dataset
- Tabular (XGBoost/LightGBM), Unsupervised (Isolation Forest), Sequence (LSTM/GRU), Ensemble models
- Adaptive learning — operator labels retrain the model automatically
- Accuracy trend tracking and model degradation alerts

### IoT
- MQTT and HTTP device adapters
- Device registration, heartbeat, disconnect/reconnect handling
- Control signal queue (SHUTDOWN / DE_RATE / RUN)
- Edge device management

### Deployment
- **Frontend** — Vercel (free tier)
- **Backend** — Render (free tier, FastAPI + Uvicorn)
- **Database** — Neon Postgres (free tier, migrated from SQLite)
- **Mobile** — installable PWA (Add to Home Screen on Android/iOS)

---

## Quick Start (Local)

### Prerequisites
- Python 3.12+
- Node.js 18+
- Git

### 1. Clone
```bash
git clone https://github.com/LakshmiNarayana124/Miniproject5.git
cd Miniproject5
```

### 2. Backend
```bash
cd Backend
pip install -r requirements.txt
# Set required env var
set INTELLIWATCH_SECRET_KEY=your-64-char-hex-secret
uvicorn server:app --host 0.0.0.0 --port 8000
```

### 3. Frontend
```bash
cd frontend
npm install
npm run dev
```

Open **https://localhost:5173**

---

## Environment Variables

### Backend (`Backend/.env`)
| Variable | Required | Description |
|---|---|---|
| `INTELLIWATCH_SECRET_KEY` | ✅ | 64-char hex string for JWT signing |
| `FIREBASE_PROJECT_ID` | For Google login | Firebase project ID |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | Optional | Service account JSON (enables phone OTP token verification) |
| `DATABASE_URL` | For Neon | Postgres connection string |

### Frontend (`frontend/.env.local`)
| Variable | Required | Description |
|---|---|---|
| `VITE_API_URL` | ✅ | Backend URL (use `/` for same-origin via Vite proxy) |
| `VITE_FIREBASE_API_KEY` | For Firebase auth | Firebase web config |
| `VITE_FIREBASE_AUTH_DOMAIN` | For Firebase auth | Firebase web config |
| `VITE_FIREBASE_PROJECT_ID` | For Firebase auth | Firebase project ID |
| `VITE_FIREBASE_MESSAGING_SENDER_ID` | For Firebase auth | Firebase web config |
| `VITE_FIREBASE_APP_ID` | For Firebase auth | Firebase web config |

---

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for full Render + Vercel + Neon setup.

**Quick links:**
- Firebase Console → Authentication → Enable Google + Phone sign-in methods
- Add your domain to Firebase → Authorized domains
- Render → Set `INTELLIWATCH_SECRET_KEY` and `FIREBASE_PROJECT_ID`

---

## Project Structure

```
IntelliWatch_PC_Ready/
├── Backend/              # FastAPI backend
│   ├── server.py         # Main FastAPI app
│   ├── auth.py           # JWT + Firebase authentication
│   ├── database.py       # SQLite / Neon Postgres adapter
│   ├── training_pipeline.py  # ML model training (KAIST)
│   ├── inference.py      # Live anomaly detection
│   ├── iot_layer.py      # MQTT/HTTP IoT adapters
│   ├── learning_system.py    # Adaptive retraining
│   ├── obs_service.py    # Model observability
│   └── tests/            # 224 property + unit tests
├── frontend/             # React + Vite frontend
│   ├── src/
│   │   ├── App.jsx       # Root app + routing
│   │   ├── components/   # All UI components
│   │   │   ├── LoginPage.jsx     # Auth (password/Google/OTP)
│   │   │   ├── ProfilePage.jsx   # User profile
│   │   │   ├── Navbar.jsx        # Navigation
│   │   │   ├── SensorExplorer.jsx
│   │   │   └── ...
│   │   └── firebase.js   # Firebase SDK init
│   └── public/
│       ├── manifest.json # PWA manifest
│       └── sw.js         # Service worker
├── render.yaml           # Render deployment blueprint
├── vercel.json           # Vercel deployment config
├── migrate_sqlite_to_neon.py  # SQLite → Neon migration
└── DEPLOYMENT.md         # Full deployment guide
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19, Vite 8, React Router 7, Recharts, Three.js |
| Backend | FastAPI, Uvicorn, PyJWT, Argon2 |
| ML | XGBoost, scikit-learn, ONNX Runtime |
| Auth | Firebase Auth (Google + Phone), custom JWT |
| Database | SQLite (local), Neon Postgres (production) |
| IoT | MQTT (paho), HTTP (httpx) |
| AI Vision | Google Gemini |
| Deployment | Vercel, Render, Neon |

---

## License

Private project — KAIST dataset used under academic license.
