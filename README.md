# IntelliWatch

> **Intelligent condition-monitoring and safety-actuation system for industrial equipment.**

IntelliWatch reads live sensor data (vibration, temperature, electrical current) from physical hardware, classifies equipment health using machine learning, and **automatically acts on anomalies** — dispatching control signals that shut down or de-rate equipment, switching physical relay channels, and updating an LCD display in real time.

---

## Live Deployment

| Component | Platform | URL |
|---|---|---|
| **Frontend** | Vercel | https://miniproject5.vercel.app |
| **Backend API** | Render | https://intelliwatch-backend.onrender.com |
| **API Docs** | Render (Swagger) | https://intelliwatch-backend.onrender.com/docs |
| **Health Check** | Render | https://intelliwatch-backend.onrender.com/health |
| **Database** | Neon Postgres | https://console.neon.tech/app/projects/gentle-snow-07661904 |

---

## Architecture

```
Physical Sensors (Raspberry Pi)
  vibration (ADXL345 · I²C) + temperature (DS18B20 · 1-Wire) + current (ACS712 · SPI/ADC)
        │
        │  HTTP POST  /iot/data/{device_id}
        ▼
┌─────────────────────────────────────────────────┐
│  Backend  (FastAPI · Python 3.11 · Render)      │
│                                                  │
│  iot_layer.py        ← device auth + validation │
│  intelliwatch_brain  ← ML: NORMAL/WARNING/CRITICAL│
│  equipment_controller← SHUTDOWN / DE_RATE / RUN │
│  lcd_relay_module    ← GPIO relay + HD44780 LCD  │
│  database.py         ← Neon Postgres / SQLite    │
│  auth.py             ← JWT + role-based access   │
│  chatbot_api.py      ← Bolt AI (Dify Chatflow)  │
└─────────────────────────────────────────────────┘
        │  REST + WebSocket
        ▼
┌─────────────────────────────────────────────────┐
│  Frontend  (React 19 · Vite 8 · Vercel)         │
│                                                  │
│  Login page      ← SVG logo · floating elements │
│  Sensor dashboard← live charts · status cards   │
│  Alert log       ← confirm/dismiss · PDF report  │
│  ML status panel ← accuracy · learned band      │
│  Bolt chatbot    ← multilingual · draggable FAB  │
│  3D Explorer     ← virtual hardware workbench    │
│  Leaderboard     ← TenderWatch rankings          │
│  User management ← admin panel                   │
└─────────────────────────────────────────────────┘
```

---

## Role-Based Access

| Role | Live sensors | Control signals | Manage |
|---|---|---|---|
| **Operator** | ✅ + reason device stopped | ❌ | — |
| **Maintenance Engineer** | ✅ | ✅ SHUTDOWN / DE_RATE / RUN | — |
| **Admin** | ✅ | ✅ | ✅ users + IoT devices |

Anomaly detection is **automated** — the ML brain fires a control signal the moment status changes without waiting for a human. Manual dispatch is role-gated (Engineer / Admin only).

---

## IoT Integration (LCD + Relay)

```python
from lcd_relay_module import LCDRelayEdgeAdapter, create_lcd_relay_actuator

adapter = LCDRelayEdgeAdapter(
    device_id="lcd-relay-01",
    actuator=create_lcd_relay_actuator(),   # HD44780 LCD + 4-ch relay
)
hs = iot_layer.register_device(adapter)
iot_layer.authenticate(hs.device_id, hs.device_credential)
```

| Intent | Relay channels | LCD display |
|---|---|---|
| `RUN` | MAIN on, INDICATOR on | `SYSTEM : RUN / STATUS : NORMAL` |
| `DE_RATE` | MAIN + DERATE on | `SYSTEM : DERATE / STATUS : WARNING` |
| `SHUTDOWN` | All off (fail-safe) | `SYSTEM : STOP / STATUS : CRITICAL` |

Hardware libs (`smbus2`, `RPi.GPIO`) are optional — backend imports cleanly anywhere.

---

## Safety Design

- Relays de-energise on startup and on any `SHUTDOWN` or unknown intent (fail-safe)
- Every control dispatch recorded immutably in the audit trail
- CRITICAL latching — only `NORMAL` status releases a latch (no silent downgrade)
- Payload validation: size limits, finite-value checks, constant-time credential comparison

> ⚠️ Verify relay polarity with a multimeter on first bring-up. Keep a hardwired e-stop in series with the main relay for real machinery.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19, Vite 8, Recharts, Three.js |
| Backend | Python 3.11, FastAPI, psycopg2, WebSockets, httpx |
| Database | Neon Postgres (production) / SQLite (local fallback) |
| Edge hardware | Raspberry Pi, ADXL345, DS18B20, ACS712, HD44780 LCD, relay board |
| Auth | JWT, role-based access control, session versioning |
| AI Chatbot | Bolt — EN/HI/KN/TA/TE, Dify Chatflow integration, offline KB fallback |

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

## Deployment Guide

### Vercel — Frontend

1. Connect GitHub → `Miniproject5` → branch `clean-start`
2. **Root Directory:** `frontend` · **Framework:** Vite
3. Add env var: `VITE_API_URL = https://intelliwatch-backend.onrender.com`
4. Deploy → live at `https://miniproject5.vercel.app`

### Render — Backend

`render.yaml` at repo root is pre-configured. Connect GitHub → `Miniproject5`.

Add these env vars in Render dashboard:

| Key | Value |
|---|---|
| `INTELLIWATCH_SECRET_KEY` | `0423617d89103f8e1825ab72354b0b04f051c0c4e5582748970153f837deb9850d43227a44e051220330545156d7079517809210e502cc998de69ebe59447f49` |
| `DATABASE_URL` | *(Neon connection string)* |
| `INTELLIWATCH_CORS_ORIGINS` | `https://miniproject5.vercel.app` |

### Neon — Database

Project `gentle-snow-07661904` already provisioned. 19 tables created automatically on first backend startup. Connect via `DATABASE_URL` env var on Render.

### Edge Device (Raspberry Pi)

Point HTTP push URL at the Render backend:
```
POST https://intelliwatch-backend.onrender.com/iot/data/{device_id}
Header: X-Device-Credential: <device-credential>
```

---

## Branches

| Branch | Purpose |
|---|---|
| `main` | Full source with all integrations |
| `clean-start` | Production deploy branch (Vercel + Render) |
| `feature/iot-lcd-relay-integration` | IoT feature branch |

---

## Important URLs

| Resource | URL |
|---|---|
| **Frontend (Live)** | https://miniproject5.vercel.app |
| **Backend API** | https://intelliwatch-backend.onrender.com |
| **Swagger Docs** | https://intelliwatch-backend.onrender.com/docs |
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
