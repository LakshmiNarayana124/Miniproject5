# IntelliWatch

> **Intelligent condition-monitoring and safety-actuation system for industrial equipment.**

IntelliWatch reads live sensor data (vibration, temperature, electrical current) from physical hardware, classifies equipment health using machine learning, and **automatically acts on anomalies** — dispatching control signals that shut down or de-rate equipment, switching physical relay channels, and updating an LCD display in real time.

---

## Live Deployment

| Component | Platform | URL |
|---|---|---|
| **Frontend** | Vercel | https://miniproject5.vercel.app |
| **Backend** | Render | https://intelliwatch-backend.onrender.com |
| **Database** | Neon Postgres | https://console.neon.tech/app/projects/gentle-snow-07661904 |
| **API Docs** | Render (Swagger) | https://intelliwatch-backend.onrender.com/docs |
| **Health Check** | Render | https://intelliwatch-backend.onrender.com/health |

---

## Architecture

```
Physical Sensors (Pi)
        │  HTTP push  (vibration · temperature · current)
        ▼
 Railway / Render Backend  (FastAPI + Python 3.11)
   ├── IoT Layer          — device auth, payload validation
   ├── ML Brain           — NORMAL / WARNING / CRITICAL
   ├── Equipment Controller — control signal dispatch (SHUTDOWN / DE_RATE / RUN)
   ├── LCD + Relay Module — physical actuator (GPIO + I²C)
   └── Neon Postgres      — 19 tables, persistent data
        │  WebSocket / REST
        ▼
 Vercel Frontend  (React 19 + Vite 8)
   ├── Live sensor dashboard
   ├── Control-signal banner
   ├── Alert log + Service Report
   ├── Adaptive ML status panel
   ├── Bolt AI chatbot (multilingual)
   ├── 3D Sensor Explorer
   ├── TenderWatch Leaderboard
   └── User management
```

---

## Role-Based Access

| Role | Live sensors | Act (control signals) | Manage |
|---|---|---|---|
| **Operator** | ✅ + reason device stopped | ❌ | — |
| **Maintenance Engineer** | ✅ | ✅ SHUTDOWN / DE_RATE / RUN | — |
| **Admin** | ✅ | ✅ | ✅ users + IoT devices |

Anomaly → action is **automated**: the ML brain fires a control signal the moment status changes, without waiting for a human. Manual dispatch is role-gated (Engineer / Admin only).

---

## IoT Integration (LCD + Relay)

```python
from lcd_relay_module import LCDRelayEdgeAdapter, create_lcd_relay_actuator

adapter = LCDRelayEdgeAdapter(
    device_id="lcd-relay-01",
    actuator=create_lcd_relay_actuator(),   # HD44780 LCD + 4-ch relay board
)
hs = iot_layer.register_device(adapter)
iot_layer.authenticate(hs.device_id, hs.device_credential)
```

| Intent | Relay channels | LCD |
|---|---|---|
| `RUN` | MAIN on, INDICATOR on | `SYSTEM : RUN / STATUS : NORMAL` |
| `DE_RATE` | MAIN + DERATE on | `SYSTEM : DERATE / STATUS : WARNING` |
| `SHUTDOWN` | All off (fail-safe) | `SYSTEM : STOP / STATUS : CRITICAL` |

Hardware libraries (`smbus2`, `RPi.GPIO`) are optional — backend imports cleanly anywhere.

---

## Safety Design

- Relays de-energise on startup and on any `SHUTDOWN` or unknown intent
- Every control dispatch recorded immutably in the audit trail
- Payload validation: size limits, finite-value checks, constant-time credential comparison
- CRITICAL latching — once critical, only `NORMAL` can release it (no silent downgrade)

> ⚠️ Verify relay polarity with a meter on first bring-up. Keep a hardwired e-stop in series with the main relay.

---

## Tech Stack

| Layer | Tech |
|---|---|
| Frontend | React 19, Vite 8, Recharts, Three.js |
| Backend | Python 3.11, FastAPI, psycopg2, WebSockets |
| Database | Neon Postgres (production) / SQLite (local fallback) |
| Edge | Raspberry Pi, smbus2, RPi.GPIO, HD44780 LCD, relay board |
| Auth | JWT, role-based access, session versioning |
| AI Chatbot | Bolt — multilingual (EN/HI/KN/TA/TE), Dify Chatflow integration |

---

## Running Locally

```bash
# Backend
cd Backend
pip install -r requirements.txt
uvicorn server:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

Set `INTELLIWATCH_SECRET_KEY` in `Backend/.env` before starting.

---

## Connecting Edge Hardware (Raspberry Pi)

Point the device's HTTP push URL at the live backend:

```
POST https://intelliwatch-backend.onrender.com/iot/data/{device_id}
Header: X-Device-Credential: <your-device-credential>
```

The backend validates, the brain classifies, and control signals flow back to the relay and LCD automatically.

---

## Deployment Guide

### Vercel (Frontend)

1. Connect GitHub → `Miniproject5` → branch `clean-start`
2. **Root Directory:** `frontend`
3. **Framework:** Vite
4. Add env var: `VITE_API_URL = https://intelliwatch-backend.onrender.com`
5. Deploy

### Render (Backend)

`render.yaml` at repo root is pre-configured. Connect GitHub → `Miniproject5`.

Add these env vars in the Render dashboard:

| Key | Value |
|---|---|
| `INTELLIWATCH_SECRET_KEY` | `0423617d89103f8e1825ab72354b0b04f051c0c4e5582748970153f837deb9850d43227a44e051220330545156d7079517809210e502cc998de69ebe59447f49` |
| `DATABASE_URL` | *(your Neon connection string)* |
| `INTELLIWATCH_CORS_ORIGINS` | `https://miniproject5.vercel.app` |

### Neon (Database)

Already provisioned at `gentle-snow-07661904`. Tables are created automatically on first backend startup.

---

## Branches

| Branch | Purpose |
|---|---|
| `main` | Full source with all integrations |
| `clean-start` | Production deploy branch (Vercel + Render) |
| `feature/iot-lcd-relay-integration` | IoT feature branch |

---

## Important URLs

| Resource | Link |
|---|---|
| **Frontend** | https://miniproject5.vercel.app |
| **Backend API** | https://intelliwatch-backend.onrender.com |
| **API Docs (Swagger)** | https://intelliwatch-backend.onrender.com/docs |
| **Neon Console** | https://console.neon.tech/app/projects/gentle-snow-07661904 |
| **Miniproject5 Repo** | https://github.com/LakshmiNarayana124/Miniproject5 |
| **IntelliWatch Private** | https://github.com/LakshmiNarayana124/IntelliWatch-Private |

---

## Research References

1. **Predictive Maintenance via IoT + ML** — Samatas et al., arXiv 2021. [arXiv:2103.11148](https://arxiv.org/abs/2103.11148)
2. **Real-Time Anomaly Detection in Industrial IoT** — arXiv 2026. [arXiv:2601.03085](https://arxiv.org/abs/2601.03085)
3. **ML-Based Rotary Machine Fault Detection** — Givnan et al., Liverpool John Moores University. [arXiv:2110.01447](https://arxiv.org/abs/2110.01447)
4. **Multi-Sensor Fault Signatures** — IEEE Technology Navigator. [IEEE TechNav](https://technav.ieee.org/topic/predictive-maintenance)
5. **TinyML Anomaly Detection at the Edge** — MDPI Sensors, 2023. [MDPI:2344](https://www.mdpi.com/1424-8220/23/4/2344)
6. **AI-Driven Predictive Maintenance (Industry 4.0)** — Deshmukh & Dere, IJCRT 2024. [IJCRT:2401033](https://ijcrt.org/papers/IJCRT2401033.pdf)

---

*IntelliWatch — software + hardware, end to end.*
