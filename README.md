# 👁️ IntelliWatch

> **Real-time industrial machine health monitoring — from a Raspberry Pi sensor all the way to a cloud dashboard, with ML anomaly detection built in.**

A Raspberry Pi reads vibration, temperature and current from physical sensors every second. Those readings travel over MQTT to a FastAPI backend that runs a four-model ML ensemble, classifies each reading against ISO industrial standards, and streams the results live to a React dashboard. The dashboard shows charts, fault signatures, a remaining-useful-life countdown, a 3D interactive hardware model, and an AI equipment inspector — all in the browser, on any device.

---

## ⚡ Quick Access

| | |
|---|---|
| **Live App** | https://intelliwatch-iw.vercel.app |
| **Backend API** | https://intelliwatch-backend.onrender.com |
| **API Docs** | https://intelliwatch-backend.onrender.com/docs |
| **GitHub** | https://github.com/LakshmiNarayana124/Miniproject5 |
| **Neon DB** | https://console.neon.tech |
| **Render** | https://dashboard.render.com |
| **Vercel** | https://vercel.com/dashboard |
| **Firebase** | https://console.firebase.google.com |

> Render free tier sleeps after 15 min idle. First login after sleep takes ~30 s — just wait.

---

## 🗂️ Branches

| Branch | Purpose |
|---|---|
| `main` | Production — auto-deploys to Vercel + Render |
| `feature/iot-lcd-relay-integration` | IoT hardware layer — LCD display + relay control |
| `clean-start` | Clean baseline with Postgres/Neon DB layer |
| `master` | Original Miniproject5 merge point |

---

## 🏗️ How It Works

```
Raspberry Pi  ──MQTT/HTTP──►  FastAPI Backend  ──SQL──►  Neon Postgres
  ADXL345 (vibration)            (Render)                 (serverless)
  DS18B20 (temperature)              │
  ACS712 (current)                   │ WebSocket
                                     ▼
                             React Dashboard
                               (Vercel CDN)
                                     │
                             Firebase Auth
                          (Google Sign-In / OTP)
```

**Cost: $0/month** — Vercel Hobby + Render Free + Neon Free + Firebase Spark

---

## 🔬 What the ML Does

The backend runs four models trained on the **KAIST bearing fault dataset**:

| Model | Does |
|---|---|
| XGBoost | Classifies each reading into Normal / Warning / Critical |
| Isolation Forest | Catches unusual readings that don't fit any known pattern |
| ONNX GRU | Detects anomalies across a sequence of readings over time |
| Scikit-learn Pipeline | Extracts signal features and scales them for the other models |

The combined output is mapped to **ISO 10816-3** severity zones and shown as a live status badge on the dashboard. Seven fault types are scored in real time — bearing wear, imbalance, thermal overload, electrical overload, misalignment, looseness, compound faults.

A **Remaining Useful Life** estimate projects when the machine will hit the critical threshold, shown as a banner: Stable / Warning <72 h / Soon <24 h / Imminent <4 h.

---

## 🖥️ Dashboard Pages

| Route | What you see |
|---|---|
| `/` | Live sensor cards, system status, ML fault panel, alert log |
| `/vibration` | Vibration history chart + ISO zone markers |
| `/temperature` | Temperature history + anomaly dots |
| `/current` | Current draw history + fault signatures |
| `/explorer` | 3D interactive hardware model — click any component for ML history |
| `/vision` | Upload a photo of equipment → Gemini AI analyses it |
| `/profile` | Your account, timezone, session info |
| `/about` | Project overview, standards, team |
| `/admin/users` | Create / manage users, roles, invitations (Admin only) |

---

## 🔐 Login Options

| Method | How |
|---|---|
| **Offline Demo** | Click "Offline Demo" — works with no backend, synthetic data |
| **Google Sign-In** | Click Google button → pick role (Operator / Engineer / Admin) |
| **Username + Password** | Register via API docs, then log in |
| **Phone OTP** | Enter number → SMS code (requires Firebase Blaze plan) |

---

## 🚀 Run Locally

**You need:** Python 3.11, Node.js 22, Git

### Backend
```powershell
cd Backend
python -m venv .venv && .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create `Backend\.env`:
```
INTELLIWATCH_SECRET_KEY=<python -c "import secrets; print(secrets.token_hex(32))">
DATABASE_URL=postgresql://...your-neon-url...
INTELLIWATCH_CORS_ORIGINS=http://localhost:5173
FIREBASE_PROJECT_ID=intelliwatch-66ad0
```

```powershell
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
# Docs at http://localhost:8000/docs
```

### Frontend
```powershell
cd frontend && npm install
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
# Open http://localhost:5173
```

---

## ☁️ Deployment

Push to `main` — both services redeploy automatically.

```powershell
git add .
git commit -m "your change"
git push origin main
# Vercel: ~1 min  |  Render: ~3 min  |  Neon: always on
```

### Environment Variables

**Render (Backend)**
```
INTELLIWATCH_SECRET_KEY    64-char hex
DATABASE_URL               Neon connection string
INTELLIWATCH_CORS_ORIGINS  https://intelliwatch-iw.vercel.app
FIREBASE_PROJECT_ID        intelliwatch-66ad0
```

**Vercel (Frontend)**
```
VITE_API_URL                       https://intelliwatch-backend.onrender.com
VITE_FIREBASE_API_KEY              from Firebase Console
VITE_FIREBASE_AUTH_DOMAIN          intelliwatch-66ad0.firebaseapp.com
VITE_FIREBASE_PROJECT_ID           intelliwatch-66ad0
VITE_FIREBASE_STORAGE_BUCKET       intelliwatch-66ad0.firebasestorage.app
VITE_FIREBASE_MESSAGING_SENDER_ID  174724193863
VITE_FIREBASE_APP_ID               1:174724193863:web:e09ddbd891e2cc547d5b62
```

---

## 🔌 Hardware Wiring (Raspberry Pi)

| Sensor | Interface | Pins |
|---|---|---|
| ADXL345 (vibration) | I2C | SDA=GPIO2, SCL=GPIO3 |
| DS18B20 (temperature) | 1-Wire | GPIO4 |
| ACS712 + ADS1115 (current) | I2C | SDA=GPIO2, SCL=GPIO3 (addr 0x48) |

---

## 🛠️ Tech Stack

**Frontend:** React 19, Vite 8, React Router 7, Recharts, Three.js, Firebase JS SDK, PWA

**Backend:** FastAPI, Uvicorn, scikit-learn, XGBoost, ONNX Runtime, Argon2, PyJWT, psycopg2, Paho MQTT, Google GenAI

**Infrastructure:** Vercel, Render, Neon, Firebase

**Standards:** ISO 10816-3, ISO 13373-1, ISO 13381-1, IEC 60034-1, IEC 62443

---

## 📄 License

MIT
