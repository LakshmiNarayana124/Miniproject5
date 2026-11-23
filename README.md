# IntelliWatch

**Intelligent condition-monitoring and safety-actuation system for industrial equipment.**

IntelliWatch reads live sensor data (vibration, temperature, current), classifies equipment health via ML, and automatically acts on anomalies — dispatching control signals that shut down or de-rate equipment, switching physical relay channels, and updating an LCD display in real time.

---

## Live Deployment

| Component | Platform | URL |
|---|---|---|
| Frontend | Vercel | https://frontend-five-kappa-31.vercel.app |
| Backend | Railway | https://intelliwatch-backend-production.up.railway.app |
| Database | Neon Postgres | 19 tables, persistent |

---

## Architecture

```
Sensors (Pi) → HTTP → Railway Backend → ML Brain → Control Signal
                                                        ↓
                                              Relay Module + LCD Display
                                                        ↓
                                              Neon Postgres (audit + data)
                                                        ↓
                                              Vercel Frontend (live dashboard)
```

Three layers:

1. **Edge Hardware** — Raspberry Pi with sensors, HD44780 LCD (I2C), multi-channel relay board
2. **Backend** (Python FastAPI on Railway)
   - `iot_layer.py` — device registration, auth, payload validation, MQTT/HTTP adapters
   - `intelliwatch_brain.py` — ML inference engine (NORMAL / WARNING / CRITICAL)
   - `equipment_controller.py` — anomaly → control signal (SHUTDOWN / DE_RATE / RUN), CRITICAL latching, audit trail
   - `lcd_relay_module.py` — LCD + relay actuator, fail-safe defaults, software shadow mode
   - `database.py` — dual Postgres/SQLite driver (Neon in production, SQLite locally)
   - `auth.py`, `learning_system.py`, `vision_service.py`, `chatbot_api.py`
3. **Frontend** (React/Vite on Vercel) — live sensor dashboard, control-signal banner, alert log, ML status panel, chatbot, user management

---

## Role-Based Access

| Role | See anomalies | Act (dispatch control) | Manage |
|---|---|---|---|
| **Operator** | ✅ including reason device stopped | ❌ | — |
| **Maintenance Engineer** | ✅ | ✅ SHUTDOWN / DE_RATE / RUN | — |
| **Admin** | ✅ | ✅ | ✅ devices + users |

Automated safety path runs under a system identity — anomalies trigger shutdown instantly without waiting for a human.

---

## IoT Integration

The LCD + relay actuator registers at backend startup and rides the existing control-signal delivery path:

```python
from lcd_relay_module import LCDRelayEdgeAdapter, create_lcd_relay_actuator

adapter = LCDRelayEdgeAdapter(device_id="lcd-relay-01",
                               actuator=create_lcd_relay_actuator())
hs = iot_layer.register_device(adapter)
iot_layer.authenticate(hs.device_id, hs.device_credential)
```

Intent → relay + LCD mapping:

| Intent | Relays | LCD |
|---|---|---|
| RUN | MAIN on, INDICATOR on | `SYSTEM : RUN / STATUS : NORMAL` |
| DE_RATE | MAIN + DERATE on | `SYSTEM : DERATE / STATUS : WARNING` |
| SHUTDOWN | All off (fail-safe) | `SYSTEM : STOP / STATUS : CRITICAL` |

---

## Safety Design

- Relays de-energize on startup and on any SHUTDOWN (fail-safe default)
- Data integrity: payload size limits, finite-value checks, credential constant-time comparison
- Every control dispatch recorded immutably in audit trail
- Hardware libs (`smbus2`, `RPi.GPIO`) optional — backend imports cleanly anywhere

> ⚠️ Verify relay polarity with a meter on first bring-up. Keep a hardwired e-stop in series with the main relay.

---

## Tech Stack

- **Backend:** Python 3.11, FastAPI, psycopg2, WebSockets, paho-mqtt / httpx
- **Frontend:** React 19, Vite 8, Recharts, Three.js
- **Database:** Neon Postgres (production) / SQLite (local)
- **Edge:** Raspberry Pi, smbus2, RPi.GPIO

---

## Running Locally

```bash
# Backend
cd Backend
pip install -r requirements.txt
uvicorn server:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

Set `INTELLIWATCH_SECRET_KEY` in `Backend/.env` before starting.

---

## Connecting Edge Hardware (Pi)

Change the device push URL to the live backend:
```
https://intelliwatch-backend-production.up.railway.app
```
The Pi pushes readings to `POST /iot/data/{device_id}` with `X-Device-Credential` header — the backend validates, brain classifies, and control signals flow back to relays and LCD automatically.

---

## Branches

| Branch | Purpose |
|---|---|
| `main` | Full source with all integrations |
| `clean-start` | Production deploy branch (Vercel + Railway) |
| `feature/iot-lcd-relay-integration` | IoT feature branch |

---

## Important URLs

| Resource | Link |
|---|---|
| **Frontend (Live)** | https://frontend-five-kappa-31.vercel.app |
| **Backend API (Live)** | https://intelliwatch-backend-production.up.railway.app |
| **Backend Health Check** | https://intelliwatch-backend-production.up.railway.app/health |
| **API Docs (Swagger)** | https://intelliwatch-backend-production.up.railway.app/docs |
| **Database (Neon)** | https://console.neon.tech/app/projects/gentle-snow-07661904 |
| **GitHub — Miniproject5** | https://github.com/LakshmiNarayana124/Miniproject5 |
| **GitHub — IntelliWatch Private** | https://github.com/LakshmiNarayana124/IntelliWatch-Private |
| **Railway Dashboard** | https://railway.com/project/2f8ca63a-580d-42ba-84e3-f2006b1789d7 |
| **Vercel Dashboard** | https://vercel.com/n0t7h1in-g/frontend |

---

## Research References

This project is grounded in published research from IEEE, arXiv, and MDPI:

1. **Predictive Maintenance via IoT + ML** — Samatas et al., *Predictive Maintenance: Bridging Artificial Intelligence and IoT*, arXiv 2021. Establishes the framework of combining sensor streams with ML for proactive fault detection. [arXiv:2103.11148](https://arxiv.org/abs/2103.11148)

2. **Real-Time Anomaly Detection in Industrial IoT** — *Real-Time Adaptive Anomaly Detection in Industrial IoT Environments*, arXiv 2026. Covers adaptive ML methods for multi-dimensional IoT sensor data, directly applicable to vibration + temperature + current fusion used in IntelliWatch. [arXiv:2601.03085](https://arxiv.org/abs/2601.03085)

3. **ML-Based Rotary Machine Fault Detection** — Givnan et al., Liverpool John Moores University. Proposes a traffic-light severity system (normal / warning / critical) for industrial anomaly detection — the same NORMAL / WARNING / CRITICAL classification model IntelliWatch implements. [arXiv:2110.01447](https://arxiv.org/abs/2110.01447)

4. **Multi-Sensor Fault Signatures** — IEEE Technology Navigator, *Machine learning for predictive maintenance using IoT sensor data*. Demonstrates that combining vibration, temperature, and current signals provides richer fault signatures than any single sensor, enabling earlier failure detection. [IEEE TechNav](https://technav.ieee.org/topic/predictive-maintenance)

5. **TinyML Anomaly Detection at the Edge** — MDPI Sensors, *An Adaptable and Unsupervised TinyML Anomaly Detection System for Extreme Industrial Environments*, 2023. Covers end-to-end IoT + edge computing for industrial anomaly detection, relevant to IntelliWatch's edge-device architecture. [MDPI:2344](https://www.mdpi.com/1424-8220/23/4/2344)

6. **AI-Driven Predictive Maintenance (Industry 4.0)** — Deshmukh & Dere, Terna Engineering College / University of Mumbai, IJCRT 2024. Addresses the shift from reactive to proactive maintenance using IoT sensor data and ML in Industry 4.0 environments. [IJCRT:2401033](https://ijcrt.org/papers/IJCRT2401033.pdf)

---

_IntelliWatch — software + hardware, end to end._
