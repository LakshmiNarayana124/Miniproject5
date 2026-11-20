# IntelliWatch

Real-time industrial condition monitoring and anomaly detection.  
Raspberry Pi edge sensors → FastAPI ML backend → React dashboard.

---

## Live URLs

| Service | URL |
|---|---|
| **Frontend** | https://intelliwatch-iw.vercel.app |
| **Backend API** | https://intelliwatch-backend-production.up.railway.app |
| **API Docs** | https://intelliwatch-backend-production.up.railway.app/docs |
| **Database** | Neon Postgres (serverless) |

---

## What It Does

Three sensor channels (vibration ADXL345, temperature DS18B20, current ACS712) stream from a Raspberry Pi over MQTT/HTTP to a FastAPI backend. The backend runs a four-model ML ensemble (XGBoost + LightGBM + Isolation Forest + LSTM/GRU trained on the KAIST bearing fault dataset), classifies each reading against ISO 10816-3 / IEC 60034-1 severity zones, identifies the fault type, and projects a remaining useful life estimate. The React dashboard shows all of this live.

**Monitoring** — live area charts, ISO severity zones, anomaly markers, session stats, alert log with operator feedback, one-click CSV+JSON audit export (IEC 62443).

**Fault signatures** — 7-fault catalogue (bearing wear, imbalance, thermal overload, electrical overload, misalignment, looseness, compound) scored per ISO 10816-3 / ISO 13373-1, shown as confidence chips in the ML panel.

**RUL estimate** — least-squares slope on rolling anomaly score projects when the critical threshold will be crossed (ISO 13381-1). Banner: stable / warning <72h / soon <24h / imminent <4h.

**3D Explorer** — interactive Three.js hardware assembly with per-component info and ML history replay.

**Equipment Vision** — Gemini AI photo analysis: component identification, working principle, monitoring recommendations.

**TenderWatch Leaderboard** — 7 Indian industrial organisations benchmarked live by Health Score (ISO 55000), Uptime (ISO 22400-2), MTBF (ISO 14224), and anomaly response latency.

**AI Assistant (Bolt)** — Dify Chatflow for authenticated sessions; multilingual local knowledge base for demo (EN/HI/KN/TA/TE). Voice input + TTS.

**Auth** — password (Argon2 + JWT), Google Sign-In (Firebase), Phone OTP (Firebase). Offline Demo needs no credentials.

**PWA** — installable on Android and iOS via Add to Home Screen.

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, Recharts, React Three Fiber, React Router |
| Backend | FastAPI, Uvicorn, Python 3.11 |
| ML | XGBoost, LightGBM, scikit-learn, ONNX Runtime |
| Auth | JWT, Argon2, Firebase |
| Database | SQLite (local) → Neon Postgres (production) |
| IoT | paho-mqtt, httpx |
| AI | Google Gemini, Dify |
| Deploy | Vercel + Railway + Neon |

---

## Architecture

```
Browser ──HTTPS──▶ Vercel (React PWA)
                        │  /auth /sensors /stream …
                        ▼
                   Railway (FastAPI + ML)
                        │  psycopg2
                        ▼
                   Neon (Postgres)

Raspberry Pi ──MQTT/HTTP──▶ Railway
Firebase ──ID token──▶ Railway (verify → issue JWT)
```

---

## Run Locally — Step by Step (Windows)

### Prerequisites

Install these before starting:

| Tool | Download | Check |
|---|---|---|
| Python 3.11+ | https://python.org/downloads | `python --version` |
| Node.js 18+ | https://nodejs.org | `node --version` |
| Git | https://git-scm.com | `git --version` |
| mkcert | https://github.com/FiloSottile/mkcert/releases | `mkcert --version` |

---

### Step 1 — Clone the repository

```bash
git clone https://github.com/LakshmiNarayana124/Miniproject5.git
cd Miniproject5
```

---

### Step 2 — Generate a trusted local HTTPS certificate (one-time)

```bash
mkcert -install
cd certs
mkcert -cert-file intelliwatch-local.crt -key-file intelliwatch-local.key localhost 127.0.0.1
cd ..
```

This installs a local CA into your OS trust store so the browser accepts the cert without warnings.

---

### Step 3 — Set up and start the Backend

Open a terminal, navigate to the project, then:

```bash
cd Backend
pip install -r requirements.txt
```

Create a secret key (run once, save the output):

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Set environment variables and start the server:

```bash
# Windows Command Prompt
set INTELLIWATCH_SECRET_KEY=<paste-your-64-char-hex-here>
set INTELLIWATCH_CORS_ORIGINS=https://localhost:5173
uvicorn server:app --host 0.0.0.0 --port 8000 --reload --ssl-certfile ../certs/intelliwatch-local.crt --ssl-keyfile ../certs/intelliwatch-local.key
```

```bash
# Windows PowerShell
$env:INTELLIWATCH_SECRET_KEY = "<paste-your-64-char-hex-here>"
$env:INTELLIWATCH_CORS_ORIGINS = "https://localhost:5173"
uvicorn server:app --host 0.0.0.0 --port 8000 --reload --ssl-certfile ../certs/intelliwatch-local.crt --ssl-keyfile ../certs/intelliwatch-local.key
```

You should see:
```
IntelliWatch database initialized successfully!
[startup] Authentication security storage ready
[startup] IntelliWatchBrain ready
INFO: Application startup complete.
```

API docs available at: **https://localhost:8000/docs**

---

### Step 4 — Set up and start the Frontend

Open a **second terminal**:

```bash
cd frontend
npm install
npm run dev
```

You should see:
```
VITE v8.3.5  ready in 1049 ms
➜  Local:   https://localhost:5173/
➜  Network: https://192.168.x.x:5173/
```

Open **https://localhost:5173** in your browser.

---

### Step 5 — Log in or explore

| Option | How |
|---|---|
| **Offline Demo** | Click **Enter Offline Demo** — no account needed, full simulation |
| **Register** | Click **📊 Operator** or **🔧 Engineer** in the "New here?" strip |
| **Sign in** | Enter username + password you registered with |
| **Google login** | Click the **Google** auth tab (requires Firebase config) |
| **Phone OTP** | Click the **Phone OTP** tab (requires Firebase Blaze plan) |

---

### Troubleshooting

| Symptom | Fix |
|---|---|
| "Backend unavailable" on login page | Backend not running — check Step 3 terminal for errors |
| Browser shows cert warning | Run `mkcert -install` again, restart browser |
| Port already in use | `netstat -ano \| findstr :8000` then kill that PID |
| `pip install` fails | Upgrade pip: `python -m pip install --upgrade pip` |
| npm install fails | Delete `node_modules` and `package-lock.json`, run again |

---

## Accounts

Registration is open when the backend is reachable:

| Role | Access |
|---|---|
| **Operator** | Monitor sensors, review alerts, submit ML feedback |
| **Maintenance Engineer** | All above + control signals, calibration, maintenance dispatch |
| **Administrator** | Full access — requires invitation token from existing admin |

---

## Environment Variables

### Backend (`Backend/.env`)

| Variable | Required | Description |
|---|---|---|
| `INTELLIWATCH_SECRET_KEY` | ✅ | 64-char hex string for JWT signing |
| `INTELLIWATCH_CORS_ORIGINS` | ✅ | Comma-separated allowed frontend origins |
| `DATABASE_URL` | Production | Neon Postgres connection string |
| `FIREBASE_PROJECT_ID` | Firebase auth | Firebase project ID |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | Phone OTP | Service account JSON |

### Frontend (`frontend/.env.local`)

| Variable | Required | Description |
|---|---|---|
| `VITE_API_URL` | ✅ | Backend URL — use `/` for local (Vite proxy), full URL for production |
| `VITE_FIREBASE_API_KEY` | Firebase | Firebase web API key |
| `VITE_FIREBASE_AUTH_DOMAIN` | Firebase | e.g. `project.firebaseapp.com` |
| `VITE_FIREBASE_PROJECT_ID` | Firebase | Firebase project ID |
| `VITE_FIREBASE_MESSAGING_SENDER_ID` | Firebase | Sender ID |
| `VITE_FIREBASE_APP_ID` | Firebase | App ID |

---

## Deploy

Full guide: [DEPLOYMENT.md](DEPLOYMENT.md)

**Neon** — [neon.tech](https://neon.tech) → New Project → copy connection string → `DATABASE_URL` in Railway.

**Railway** — [railway.app](https://railway.app) → New Project → GitHub → `Miniproject5` → Root Directory: `Backend` → set env vars → Deploy.

**Vercel** — [vercel.com](https://vercel.com) → New Project → GitHub → `Miniproject5` → set `VITE_API_URL` + `VITE_FIREBASE_*` → Deploy.

**Firebase** → Authentication → enable Google + Phone → add your Vercel domain to Authorized Domains.

---

## Standards Referenced

ISO 10816-3 · IEC 60034-1 · IEC 60947-4-1 · NEMA MG-1 · ISO 13373-1 · ISO 13381-1 · ISO 55000 · ISO 22400-2 · ISO 14224 · IEC 62443
