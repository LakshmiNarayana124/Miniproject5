# 👁️ IntelliWatch

> Real-time industrial machine health monitoring — Raspberry Pi sensors → ML backend → live cloud dashboard.

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

> Render free tier sleeps after 15 min idle. First request takes ~30 s.

---

## 🏗️ Architecture

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

## 🔑 Prototype Credentials

| Username | Role |
|---|---|
| `watchtower_01` | Admin |
| `operator01` | Operator |
| `engineer01` | Maintenance Engineer |

Use the Password tab on the login page.

---

## 🗂️ Branches

| Branch | Purpose |
|---|---|
| `clean-start` | **Production** — auto-deploys to Vercel + Render |
| `feature/iot-lcd-relay-integration` | IoT hardware layer — LCD + relay control |

---

## 🔬 What the ML Does

Four models trained on the [KAIST bearing fault dataset](https://github.com/KAIST-VCLAB/KAIST-Bearing):

| Model | Role |
|---|---|
| XGBoost | Classifies readings → Normal / Warning / Critical |
| Isolation Forest | Catches anomalies that don't fit any known pattern |
| ONNX GRU | Detects anomalies across a time sequence |
| Scikit-learn Pipeline | Feature extraction and scaling |

Output is mapped to **ISO 10816-3** severity zones. Seven fault types scored in real time — bearing wear, imbalance, thermal overload, electrical overload, misalignment, looseness, compound faults. A Remaining Useful Life estimate shows Stable / Warning / Soon / Imminent.

---

## 🖥️ Dashboard Pages

| Route | What you see |
|---|---|
| `/` | Live sensor cards, ML fault panel, alert log |
| `/vibration` | Vibration history + ISO zone markers |
| `/temperature` | Temperature history + anomaly dots |
| `/current` | Current draw + fault signatures |
| `/explorer` | 3D hardware model — click any component for ML history |
| `/vision` | Upload equipment photo → Gemini AI inspection |
| `/about` | Project overview, standards, team |
| `/admin/users` | User management (Admin only) |

---

## 🔐 Login Options

| Method | How |
|---|---|
| **Offline Demo** | Works with no backend — synthetic data |
| **Google Sign-In** | Pick role (Operator / Engineer / Admin) |
| **Username + Password** | Register via API docs |
| **Phone OTP** | SMS code (requires Firebase Blaze plan) |

---

## 🚀 Run Locally

**Requirements:** Python 3.11, Node.js 22, Git

```powershell
# Backend
cd Backend
python -m venv .venv && .venv\Scripts\Activate.ps1
pip install -r requirements.txt
# create Backend\.env with INTELLIWATCH_SECRET_KEY, DATABASE_URL,
# INTELLIWATCH_CORS_ORIGINS=http://localhost:5173, FIREBASE_PROJECT_ID=intelliwatch-66ad0
uvicorn server:app --host 0.0.0.0 --port 8000 --reload

# Frontend
cd frontend && npm install
# create frontend\.env.local with VITE_API_URL=http://localhost:8000 + Firebase keys
npm run dev
```

---

## ☁️ Deployment

Push to `clean-start` — both services redeploy automatically.

```powershell
git add .
git commit -m "your change"
git push miniproject5 HEAD:clean-start
# Vercel: ~1 min  |  Render: ~3 min  |  Neon: always on
```

**Render env vars:** `INTELLIWATCH_SECRET_KEY`, `DATABASE_URL`, `INTELLIWATCH_CORS_ORIGINS`, `FIREBASE_PROJECT_ID`

**Vercel env vars:** `VITE_API_URL=https://intelliwatch-backend.onrender.com` + Firebase config keys

---

## 🔌 Hardware Wiring

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

## 📚 Research Basis

Papers this project draws on:

1. **Decker, Lebacher & Tresp (2023)** — *Does Your Model Think Like an Engineer? Explainable AI for Bearing Fault Detection with Deep Learning* — IEEE ICASSP 2023. Informs the XGBoost fault classification and feature attribution approach used here.
   [arXiv:2310.12967](https://arxiv.org/abs/2310.12967) · [DOI](https://doi.org/10.1109/ICASSP49357.2023.10096396)

2. **Alam et al. (2025)** — *Physics-Informed Multimodal Bearing Fault Classification under Variable Operating Conditions using Transfer Learning* — validates the KAIST bearing dataset as a cross-domain benchmark and the multi-signal (vibration + current) approach used here, achieving 98% accuracy on KAIST.
   [arXiv:2508.07536](https://arxiv.org/abs/2508.07536)

3. **Liu et al. (2008)** — *Isolation Forest* — IEEE ICDM 2008. The foundational algorithm for the unsupervised anomaly scorer in this system.
   [DOI:10.1109/ICDM.2008.17](https://doi.org/10.1109/ICDM.2008.17)

4. **Chen & Guestrin (2016)** — *XGBoost: A Scalable Tree Boosting System* — ACM KDD 2016. The classifier at the core of the ensemble.
   [arXiv:1603.02754](https://arxiv.org/abs/1603.02754) · [DOI](https://doi.org/10.1145/2939672.2939785)

5. **Cho et al. (2014)** — *Learning Phrase Representations using RNN Encoder–Decoder* — EMNLP 2014. Introduces the GRU architecture used in the ONNX sequence model.
   [arXiv:1406.1078](https://arxiv.org/abs/1406.1078)

---

## 📄 License

MIT
