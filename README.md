# IntelliWatch

**Intelligent condition-monitoring and safety-actuation system for industrial equipment.**

IntelliWatch reads live sensor data from physical equipment (vibration, temperature, electrical current), runs it through a machine-learning inference engine to classify equipment health, and when something is wrong it does more than raise an alarm: it dispatches a control signal that can shut the machine down or de-rate it, and drives an LCD display and relay module so the action is both visible and physical.

> This is the **private** working copy (`IntelliWatch-Private`).

---

## What it does

- **Hardware → App (telemetry in):** edge devices (e.g. a Raspberry Pi with sensors) push readings to the backend over HTTP. Readings are authenticated and validated before they ever touch the inference engine or dashboard.
- **Anomaly detection:** an ML "brain" classifies each snapshot as `NORMAL`, `WARNING`, or `CRITICAL`.
- **App → Hardware (control out):** the detected status maps to a control signal — `CRITICAL → SHUTDOWN`, `WARNING → DE_RATE`, `NORMAL → RUN` — and is relayed to physical actuators: relay channels switch and an LCD shows the live status.
- **Automated safety:** when the brain itself flags a critical anomaly, the system acts immediately under a system identity rather than waiting for a human.

## Architecture

Three layers that talk over HTTP:

1. **Edge hardware** — sensors + an LCD character display + a relay board (HD44780 over I2C / PCF8574, multi-channel GPIO relays).
2. **Backend** — a Python FastAPI server:
   - `iot_layer.py` — IoT integration layer: edge-device protocol, MQTT/HTTP adapters, device registration, credential auth, payload validation, heartbeat, control-signal relay.
   - `intelliwatch_brain.py` — ML inference engine.
   - `equipment_controller.py` — status → control-signal dispatch, CRITICAL latching, retry, fail-safe alerts, immutable audit trail.
   - `lcd_relay_module.py` — LCD + relay actuator (fail-safe defaults, graceful software-shadow mode when hardware libs are absent).
   - `auth.py`, `database.py`, `learning_system.py`, `vision_service.py`, `chatbot_api.py`, and more.
3. **Frontend** — React (Vite): live sensor dashboard, control-signal banner, alert log, ML status panel, sensor explorer, chatbot, user management, login.

## Role-based access

| Role | See anomalies (read) | Act (dispatch a control signal) | Manage |
|---|---|---|---|
| **Operator** | yes — including *why* a device stopped | no | — |
| **Maintenance Engineer** | yes | yes — SHUTDOWN / DE_RATE / RUN | — |
| **Admin** | yes | yes | yes — device registration, users |

The manual dispatch path is role-gated (engineer / admin); the automated safety path runs under a system identity so emergency shutdowns are never blocked on a human.

## Safety design

- **Fail-safe defaults:** relays de-energize on startup and on any `SHUTDOWN` or unknown intent.
- **Data integrity:** payload size limits, finite-value checks, quality enums, and rejection of simulation-tagged sources; credentials checked with constant-time comparison.
- **Audit:** every control dispatch is recorded immutably.
- **Graceful degradation:** hardware libraries are optional; the backend imports and runs anywhere with no errors.

> ⚠️ For real machinery, software fail-safe is necessary but not sufficient. Verify relay polarity with a meter on first bring-up, ensure relays drop out on power loss, and keep a hardwired emergency stop in series with the main relay.

## Tech stack

- **Backend:** Python, FastAPI, WebSocket streams, SQLite (Neon-migratable), paho-mqtt / httpx (optional).
- **Frontend:** React, Vite, Recharts.
- **Edge:** Raspberry Pi, I2C LCD, GPIO relays, smbus2 / RPi.GPIO.

## Running

- **Backend:** start the FastAPI server from `Backend/` (see `RUN_ON_WINDOWS.bat` / `startup.txt` for the project's startup commands).
- **Frontend:** from `frontend/`, `npm install` then `npm run dev` (Vite dev server).
- HTTPS / reverse-proxy config is in `Caddyfile`.

## IoT integration

The LCD + relay actuator registers automatically at backend startup and rides the existing control-signal delivery path:

```python
from lcd_relay_module import LCDRelayEdgeAdapter, create_lcd_relay_actuator

adapter = LCDRelayEdgeAdapter(device_id="lcd-relay-01", actuator=create_lcd_relay_actuator())
hs = iot_layer.register_device(adapter)
iot_layer.authenticate(hs.device_id, hs.device_credential)
```

Every `equipment_controller.dispatch(...)` then flows out to the relays and display automatically.

---

_Status: private working copy._
