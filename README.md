# IntelliWatch

**Real-Time Industrial Condition Monitoring & Anomaly Detection**

A full-stack predictive maintenance platform combining live IoT sensor data, ML-based anomaly detection, Firebase authentication, and a PWA-ready React frontend.

---

## What We Built Today

### 🔐 Firebase Authentication (Google Sign-In + Phone OTP)
- Added **Google Sign-In** tab on the login page — authenticates via Firebase popup, falls back to redirect on mobile browsers that block popups
- Added **Phone + OTP** tab with a two-field input: country code dropdown (21 countries, default 🇮🇳 +91 India) and a separate number field
- Backend verifies Firebase ID tokens using **Google's public X.509 certificates** — no service account private key required, only `FIREBASE_PROJECT_ID`
- Role selection (Operator / Engineer) is taken from the existing subrole tabs — no duplicate picker
- All Firebase error codes mapped to human-readable messages (`auth/billing-not-enabled`, `auth/configuration-not-found`, `auth/invalid-phone-number`, etc.)
- Phone OTP token exchange uses a 15-second timeout (Google's JWKS fetch can be slow on first call)

### 👤 Profile Page
- New `/profile` route available to all roles
- Flat, settings-style layout — no outer boxes, just section headers and divider rows
- Shows: full name, username, role, account type, session mode (🟢 Online / 🧪 Demo), access level (🔓 / 🔒), timezone, user ID
- **Change password** form (online accounts only) — expands inline, min 12 chars, confirm check
- **Sign out** button
- Light mode support — all text visible in both dark and light themes
- Navbar link added in industrial priority order

### 🗺️ Navbar Tab Reorder (Industrial Priority)
Order changed to reflect operational workflow:
> Dashboard → Vibration → Temperature → Current → Explorer → Vision → Admin Users → **Profile** → About

### 🕐 Timezone Selector
- Dropdown on the login card (default: India IST UTC+5:30)
- 19 zones covering India, UAE, Pakistan, Bangladesh, Sri Lanka, Nepal, UK, Europe, Russia, USA, Brazil, Japan, Singapore, Australia, NZ, UTC
- Selected timezone stored in the session user object and shown on the Profile page

### 📱 PWA Mobile App
- Added `public/sw.js` service worker — caches app shell, network-first for API calls, offline fallback
- Registered in `main.jsx` on page load
- Updated `manifest.json` — standalone display, generated 192×192 and 512×512 PNG icons
- Installable via "Add to Home Screen" on Android (Chrome) and iOS (Safari)

### 🔁 Login → Dashboard Redirect
- `BrowserRouter` now always mounts (before login) so all routes including Profile are registered immediately
- After login, `justLoggedIn` flag triggers a React Router redirect to `/` (dashboard) — no hard refresh needed
- Profile link appears in the navbar immediately after login

### 🐛 Bug Fixes
- **Firebase ADMIN role conflict** — removed ADMIN from FirebaseRolePicker (backend only accepts OPERATOR/MAINTENANCE_ENGINEER via open Firebase sign-in)
- **`setLoading(false)` after `onLogin()`** — was causing LoginPage re-render that blocked transition into the app; now only called on failure
- **`auth/configuration-not-found`** — mapped to actionable message prompting user to enable Google sign-in in Firebase Console
- **`auth/billing-not-enabled`** — mapped to message explaining Blaze plan requirement for phone SMS
- **reCAPTCHA container `display:none`** — changed to `position:fixed; z-index:-1` so Firebase invisible reCAPTCHA can initialize
- **RecaptchaVerifier explicit `.render()`** — required by Firebase modular SDK v9+
- **Profile page not visible after login** — fixed by mounting BrowserRouter before authentication state

### 🚀 Deployment Configs Added
- `render.yaml` — Render blueprint (backend + frontend, free tier)
- `vercel.json` — Vercel SPA config with rewrite rules and asset caching
- `Backend/Procfile` — Render/fly.io compatible
- `DEPLOYMENT.md` — full step-by-step guide for Neon → Render → Vercel → Firebase
- `migrate_sqlite_to_neon.py` updated to include `firebase_identities` table
- `database.py` now auto-detects `DATABASE_URL`/`NEON_DIRECT_URL` and uses Postgres

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
