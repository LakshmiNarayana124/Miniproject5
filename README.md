# IntelliWatch

Real-time industrial condition monitoring and anomaly detection — Raspberry Pi edge sensors → FastAPI ML backend → React dashboard.

---

## Live

| | URL |
|---|---|
| **App** | https://intelliwatch.vercel.app |
| **API** | https://intelliwatch-backend.up.railway.app |
| **Docs** | https://intelliwatch-backend.up.railway.app/docs |

---

## What it does

Three sensor channels (vibration ADXL345, temperature DS18B20, current ACS712) stream from a Raspberry Pi over MQTT/HTTP to a FastAPI backend. The backend runs a four-model ML ensemble (XGBoost + LightGBM + Isolation Forest + LSTM/GRU trained on the KAIST bearing fault dataset), classifies each reading against ISO 10816-3 / IEC 60034-1 severity zones, identifies the fault type, and projects a remaining useful life estimate. The React dashboard shows all of this live.

**Monitoring** — live area charts per sensor, ISO severity zones, anomaly dot markers, session statistics, alert log with operator feedback (confirm / dismiss anomaly), one-click CSV+JSON audit-trail export (IEC 62443).

**Fault signatures** — 7-fault catalogue (bearing wear, imbalance, thermal overload, electrical overload, misalignment, looseness, compound) scored per ISO 10816-3 / ISO 13373-1, shown as confidence chips in the ML panel.

**RUL estimate** — least-squares slope on the rolling anomaly score history projects when the critical threshold will be crossed (ISO 13381-1). Colour-coded banner: stable / warning <72 h / soon <24 h / imminent <4 h.

**3D Explorer** — interactive Three.js model of the hardware assembly with per-component info and ML classification history replay.

**Equipment Vision** — upload or capture a photo; Gemini AI identifies the equipment, explains its working principle, and suggests IntelliWatch monitoring applications.

**TenderWatch Leaderboard** — 7 Indian industrial organisations benchmarked live by Health Score (ISO 55000), Uptime (ISO 22400-2), MTBF (ISO 14224), and anomaly response latency.

**AI Assistant (Bolt)** — Dify Chatflow for authenticated sessions; multilingual local knowledge base for demo mode (English, Hindi, Kannada, Tamil, Telugu). Voice input + TTS.

**Auth** — password (Argon2 + JWT), Google Sign-In (Firebase), Phone OTP (Firebase). Offline Demo needs no credentials.

**PWA** — installable on Android and iOS via Add to Home Screen.

---

## Stack

| | |
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
                        │ /auth /sensors /stream …
                        ▼
                   Railway (FastAPI)
                        │ psycopg2
                        ▼
                   Neon (Postgres)

Raspberry Pi ──MQTT/HTTP──▶ Railway (FastAPI)
Firebase ──ID token──▶ Railway (verify + issue JWT)
```

---

## Run locally (HTTPS)

**Prerequisites:** Python 3.11+, Node 18+, [mkcert](https://github.com/FiloSottile/mkcert)

```bash
# 1. Clone
git clone https://github.com/LakshmiNarayana124/Miniproject5.git
cd Miniproject5

# 2. Trusted local cert (one-time)
mkcert -install
mkcert -cert-file certs/intelliwatch-local.crt \
       -key-file  certs/intelliwatch-local.key \
       localhost 127.0.0.1

# 3. Backend
cd Backend
pip install -r requirements.txt
set INTELLIWATCH_SECRET_KEY=<64-char-hex>
set INTELLIWATCH_CORS_ORIGINS=https://localhost:5173
uvicorn server:app --host 0.0.0.0 --port 8000 --reload \
  --ssl-certfile ../certs/intelliwatch-local.crt \
  --ssl-keyfile  ../certs/intelliwatch-local.key

# 4. Frontend (new terminal)
cd frontend
npm install
npm run dev
# → https://localhost:5173
```

No username needed — click **Enter Offline Demo** to explore immediately.

---

## Accounts

Registration is open when the backend is reachable. Three roles:

| Role | Can do |
|---|---|
| **Operator** | Monitor sensors, review alerts, submit ML feedback |
| **Maintenance Engineer** | All above + control signals, calibration, maintenance dispatch |
| **Administrator** | Full access — requires invitation token |

---

## Deploy

Full guide: [DEPLOYMENT.md](DEPLOYMENT.md)

**Neon** — create project → copy connection string → `DATABASE_URL` in Railway.

**Railway** — New Project → GitHub → `Miniproject5` → Root Directory: `Backend`. Set `INTELLIWATCH_SECRET_KEY`, `DATABASE_URL`, `INTELLIWATCH_CORS_ORIGINS` (your Vercel URL), `FIREBASE_PROJECT_ID`.

**Vercel** — New Project → GitHub → `Miniproject5`. Set `VITE_API_URL` (Railway URL) + `VITE_FIREBASE_*` vars. Reads `vercel.json` automatically (SPA rewrites, asset caching).

**Firebase** → Authentication → enable Google + Phone → add your Vercel domain to Authorized Domains.

---

## Standards referenced

ISO 10816-3 · IEC 60034-1 · IEC 60947-4-1 · NEMA MG-1 · ISO 13373-1 · ISO 13381-1 · ISO 55000 · ISO 22400-2 · ISO 14224 · IEC 62443
