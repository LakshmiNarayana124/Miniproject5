# -*- coding: utf-8 -*-
"""
INTELLIWATCH — FastAPI Server
Handles sensor endpoints, control signals, ML/learning, explorer, IoT, and audit.
Tasks 12.1-12.5, 15.2
"""

import asyncio
import json
import os
import time
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from auth import auth_router, require_roles, get_current_user
import database
import obs_service


# ==========================================
# APPLICATION
# ==========================================

app = FastAPI(
    title="IntelliWatch – Real-Time Anomaly Detection",
    version="2.0.0",
)

# CORS — configurable via INTELLIWATCH_CORS_ORIGINS env var for cloud/mobile
# deployment (comma-separated list of origins).  Falls back to localhost defaults.
_raw_origins = os.environ.get("INTELLIWATCH_CORS_ORIGINS", "")
_extra_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]
_allowed_origins = [
    # HTTP — local dev (default)
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",   # vite preview
    "http://127.0.0.1:4173",
    # HTTPS — local dev with npm run dev:https / uvicorn SSL
    "https://localhost:5173",
    "https://127.0.0.1:5173",
    "https://localhost:4173",
    "https://127.0.0.1:4173",
] + _extra_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)


# ==========================================
# GLOBAL SINGLETONS (wired at startup, task 15.2)
# ==========================================

_controller = None
_iot_layer = None
_learning_system = None
_brain = None          # IntelliWatchBrain singleton

# WebSocket status-stream clients
_status_clients: set = set()

# Sensor-data WebSocket clients (receive live readings every poll tick)
_sensor_clients: list = []


# ==========================================
# STARTUP / SHUTDOWN  (Task 15.2)
# ==========================================

@app.on_event("startup")
async def startup():
    global _controller, _iot_layer, _learning_system, _brain
    database.initialize_database()

    try:
        from iot_layer import IoTIntegrationLayer
        _iot_layer = IoTIntegrationLayer()
        _iot_layer.start_heartbeat()
    except Exception as e:
        print(f"[startup] IoT layer init warning: {e}")

    try:
        from equipment_controller import EquipmentController
        _controller = EquipmentController(iot_layer=_iot_layer)
        # Alert listener that pushes to WebSocket clients
        _controller.add_alert_listener(_broadcast_alert)
    except Exception as e:
        print(f"[startup] EquipmentController init warning: {e}")

    try:
        from learning_system import LearningSystem
        _learning_system = LearningSystem()
    except Exception as e:
        print(f"[startup] LearningSystem init warning: {e}")

    # Instantiate the Brain (orchestrates sensor→engine→calibration cycle)
    try:
        from intelliwatch_brain import IntelliWatchBrain
        _brain = IntelliWatchBrain(auto_calibrate=True)
        print("[startup] IntelliWatchBrain ready")
    except Exception as e:
        print(f"[startup] IntelliWatchBrain init warning: {e}")

    # Ensure explorer model exists
    try:
        from explorer_ml import train_explorer_model
        from model_registry import registry
        if registry.active_model("explorer") is None:
            train_explorer_model()
    except Exception as e:
        print(f"[startup] Explorer model init warning: {e}")

    # Run initial degradation check
    obs_service.check_model_degradation()


@app.on_event("shutdown")
async def shutdown():
    if _iot_layer:
        try:
            _iot_layer.stop_heartbeat()
        except Exception:
            pass


def _broadcast_alert(alert):
    """Push alert to all WebSocket status-stream clients.

    Safe to call from background threads: schedules coroutines on the
    running event loop via run_coroutine_threadsafe instead of the
    thread-unsafe asyncio.create_task.
    """
    msg = json.dumps(alert, default=str)

    async def _send_all():
        for ws in list(_status_clients):
            try:
                await ws.send_text(msg)
            except Exception:
                _status_clients.discard(ws)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(_send_all(), loop)
    except Exception:
        pass


# ==========================================
# PERMISSIONS
# ==========================================

sensor_access = require_roles("ADMIN", "OPERATOR", "MAINTENANCE_ENGINEER")
admin_access = require_roles("ADMIN")
actuation_access = require_roles("ADMIN", "MAINTENANCE_ENGINEER")
operator_access = require_roles("OPERATOR", "MAINTENANCE_ENGINEER")
# Label submission is also allowed for ADMIN (admins should be able to
# provide ground-truth labels, e.g. during initial system commissioning)
label_access = require_roles("ADMIN", "OPERATOR", "MAINTENANCE_ENGINEER")


# ==========================================
# SENSOR MODELS
# ==========================================

class VibrationData(BaseModel):
    x_g: float; y_g: float; z_g: float; magnitude_g: float

class TemperatureData(BaseModel):
    celsius: float; fahrenheit: float

class CurrentData(BaseModel):
    rms_current_a: float; dc_current_a: float; raw_voltage_v: float

class AllSensorsData(BaseModel):
    timestamp: float; vibration: VibrationData
    temperature: TemperatureData; current: CurrentData; status: str = "ok"


# ==========================================
# HEALTH
# ==========================================

@app.get("/", tags=["Health"])
async def root():
    return {"project": "IntelliWatch", "status": "running", "version": "2.0.0"}

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "timestamp": time.time()}


# ==========================================
# SENSOR ENDPOINTS
# ==========================================

@app.get("/sensors/vibration", response_model=VibrationData, tags=["Sensors"],
         dependencies=[Depends(sensor_access)])
async def get_vibration():
    from sensor_reader import read_vibration
    r = read_vibration()
    meta = r.get("metadata", {})
    return VibrationData(
        x_g=meta.get("x", 0.0),
        y_g=meta.get("y", 0.0),
        z_g=meta.get("z", 0.0),
        magnitude_g=r.get("value", 0.0),
    )


@app.get("/sensors/temperature", response_model=TemperatureData, tags=["Sensors"],
         dependencies=[Depends(sensor_access)])
async def get_temperature():
    from sensor_reader import read_temperature
    r = read_temperature()
    celsius = r.get("value", 25.0)
    return TemperatureData(celsius=celsius, fahrenheit=celsius * 9 / 5 + 32)


@app.get("/sensors/current", response_model=CurrentData, tags=["Sensors"],
         dependencies=[Depends(sensor_access)])
async def get_current():
    from sensor_reader import read_current
    r = read_current()
    rms = r.get("value", 0.0)
    return CurrentData(rms_current_a=rms, dc_current_a=rms * 0.95, raw_voltage_v=rms * 0.167)


@app.get("/sensors/all", tags=["Sensors"],
         dependencies=[Depends(sensor_access)])
async def get_all_sensors():
    """
    Read all sensors in one call.  Returns a flat dict with vibration,
    temperature, and current readings so the frontend can update in a single
    HTTP round-trip.
    """
    from sensor_reader import read_all_sensors
    readings = read_all_sensors()
    v = readings.get("vibration", {})
    t = readings.get("temperature", {})
    c = readings.get("current", {})

    # If the brain is available, run a full assessment cycle
    assessment = {}
    if _brain is not None:
        try:
            assessment = _brain.run_cycle()
        except Exception:
            pass

    return {
        "timestamp": time.time(),
        "vibration": {
            "value":   v.get("value"),
            "unit":    v.get("unit", "g"),
            "quality": v.get("quality", "GOOD"),
            "metadata": v.get("metadata", {}),
        },
        "temperature": {
            "value":   t.get("value"),
            "unit":    t.get("unit", "°C"),
            "quality": t.get("quality", "GOOD"),
        },
        "current": {
            "value":   c.get("value"),
            "unit":    c.get("unit", "A"),
            "quality": c.get("quality", "GOOD"),
        },
        "assessment": assessment,
    }


@app.websocket("/stream/sensors")
async def sensor_stream(websocket: WebSocket):
    """
    Push live sensor readings to the frontend every 3 seconds.
    The frontend connects here so charts update in real time without polling.
    """
    await websocket.accept()
    _sensor_clients.append(websocket)
    try:
        from sensor_reader import read_all_sensors
        while True:
            readings = read_all_sensors()
            v = readings.get("vibration", {})
            t = readings.get("temperature", {})
            c = readings.get("current", {})
            payload = {
                "ts": int(time.time() * 1000),
                "vibration":   {"value": v.get("value"), "quality": v.get("quality", "GOOD")},
                "temperature": {"value": t.get("value"), "quality": t.get("quality", "GOOD")},
                "current":     {"value": c.get("value"), "quality": c.get("quality", "GOOD")},
            }
            await websocket.send_text(json.dumps(payload))
            await asyncio.sleep(3)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        if websocket in _sensor_clients:
            _sensor_clients.remove(websocket)


# ==========================================
# TASK 12.1 — CONTROL / STATUS ENDPOINTS
# ==========================================

class DispatchRequest(BaseModel):
    intent: str
    target_equipment: Optional[str] = "default"

class AckRequest(BaseModel):
    control_signal_id: int
    equipment_state: str = ""


@app.post("/control/dispatch", tags=["Control"],
          dependencies=[Depends(actuation_access)])
async def dispatch_control(req: DispatchRequest, user=Depends(actuation_access)):
    if _controller is None:
        raise HTTPException(503, "Controller not initialized")
    from equipment_controller import PermissionDenied
    try:
        result = _controller.dispatch(
            intent=req.intent.upper(),
            status=obs_service._current_status.get("status", "NORMAL"),
            session={"role": user["role"], "username": user["username"]},
            target_equipment=req.target_equipment,
        )
        # Push to WebSocket stream
        obs_service.set_current_status(result["status"], result["intent"])
        await _push_status_update()
        return result
    except PermissionDenied as e:
        raise HTTPException(403, str(e))


@app.get("/control/current", tags=["Control"],
         dependencies=[Depends(sensor_access)])
async def get_current_control():
    return obs_service.get_system_status(_iot_layer)


@app.post("/control/ack", tags=["Control"],
          dependencies=[Depends(actuation_access)])
async def ack_control(req: AckRequest):
    if _controller is None:
        raise HTTPException(503, "Controller not initialized")
    ok = _controller.on_ack(req.control_signal_id, req.equipment_state)
    return {"acknowledged": ok, "control_signal_id": req.control_signal_id}


@app.websocket("/stream/status")
async def status_stream(websocket: WebSocket):
    """Push system status and control-signal updates to frontend (Req 3.7, 14.2)."""
    await websocket.accept()
    _status_clients.add(websocket)
    try:
        # Send current state immediately on connect
        await websocket.send_text(json.dumps(obs_service.get_system_status(_iot_layer), default=str))
        while True:
            # Keep alive; updates pushed via _push_status_update
            await asyncio.sleep(5)
            await websocket.send_text(json.dumps(obs_service.get_system_status(_iot_layer), default=str))
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in _status_clients:
            _status_clients.remove(websocket)


async def _push_status_update():
    msg = json.dumps(obs_service.get_system_status(_iot_layer), default=str)
    for ws in list(_status_clients):
        try:
            await ws.send_text(msg)
        except Exception:
            if ws in _status_clients:
                _status_clients.remove(ws)


# ==========================================
# TASK 12.2 — MODEL / LEARNING ENDPOINTS
# ==========================================

@app.get("/models/status", tags=["Models"],
         dependencies=[Depends(sensor_access)])
async def get_models_status():
    return obs_service.get_all_model_statuses()


@app.get("/models/trend/{family}", tags=["Models"],
         dependencies=[Depends(sensor_access)])
async def get_model_trend(family: str):
    return {"family": family, "trend": obs_service.get_accuracy_trend(family)}


@app.get("/models/degradation", tags=["Models"],
         dependencies=[Depends(sensor_access)])
async def get_degradation():
    return {"alerts": obs_service.check_model_degradation()}


class LabelRequest(BaseModel):
    event_id: Optional[int] = None
    label: str
    feature_vector: list
    model_version: str

class RecalibrateRequest(BaseModel):
    family: str = "tabular"


@app.post("/learning/label", tags=["Learning"],
          dependencies=[Depends(label_access)])
async def submit_label(req: LabelRequest, user=Depends(label_access)):
    if _learning_system is None:
        raise HTTPException(503, "Learning system not initialized")
    row_id = _learning_system.submit_label(
        event_id=req.event_id,
        label=req.label,
        feature_vector=req.feature_vector,
        model_version=req.model_version,
        verified_by=user["username"],
    )
    obs_service.log_event("feedback_ingestion", "label_submitted", {"row_id": row_id})
    return {"success": True, "label_id": row_id}


@app.post("/learning/recalibrate", tags=["Learning"],
          dependencies=[Depends(admin_access)])
async def trigger_recalibrate(req: RecalibrateRequest):
    if _learning_system is None:
        raise HTTPException(503, "Learning system not initialized")
    result = _learning_system.recalibrate(family=req.family)
    obs_service.log_event("recalibration", "completed", result)
    return result


# ==========================================
# TASK 12.3 — 3D EXPLORER ENDPOINTS
# ==========================================

class ExplorerClassifyRequest(BaseModel):
    arrangement: list = []
    readings: dict = {}

class ExplorerHistoryRequest(BaseModel):
    entry_type: str  # workspace_state | classification
    active_user: Optional[str] = None
    arrangement: Optional[list] = None
    classification_label: Optional[str] = None
    confidence: Optional[float] = None
    model_version: Optional[str] = None


@app.post("/explorer/classify", tags=["Explorer"],
          dependencies=[Depends(sensor_access)])
async def explorer_classify(req: ExplorerClassifyRequest):
    from explorer_ml import classify
    result = classify(req.arrangement, req.readings)
    return result


@app.post("/explorer/history", tags=["Explorer"],
          dependencies=[Depends(sensor_access)])
async def add_explorer_history(req: ExplorerHistoryRequest):
    arr_json = json.dumps(req.arrangement) if req.arrangement is not None else None
    row_id = database.save_explorer_history_entry(
        entry_type=req.entry_type,
        active_user=req.active_user,
        arrangement_json=arr_json,
        classification_label=req.classification_label,
        confidence=req.confidence,
        model_version=req.model_version,
    )
    return {"success": True, "id": row_id}


@app.get("/explorer/history", tags=["Explorer"],
         dependencies=[Depends(sensor_access)])
async def list_explorer_history(limit: int = 50):
    return database.get_explorer_history(limit)


@app.get("/explorer/history/{entry_id}", tags=["Explorer"],
         dependencies=[Depends(sensor_access)])
async def get_explorer_history_entry(entry_id: int):
    entry = database.get_explorer_history_entry(entry_id)
    if not entry:
        raise HTTPException(404, "History entry not found")
    return entry


# ==========================================
# TASK 12.4 — IOT ENDPOINTS
# ==========================================

class DeviceRegisterRequest(BaseModel):
    device_id: str
    protocol: str = "HTTP"
    capabilities: List[str] = []
    base_url: Optional[str] = None
    broker_host: Optional[str] = None


@app.post("/iot/devices", tags=["IoT"],
          dependencies=[Depends(admin_access)])
async def register_iot_device(req: DeviceRegisterRequest):
    if _iot_layer is None:
        raise HTTPException(503, "IoT layer not initialized")
    from iot_layer import HTTPAdapter, MQTTAdapter
    caps = set(req.capabilities)
    if req.protocol.upper() == "MQTT" and req.broker_host:
        device = MQTTAdapter(req.device_id, req.broker_host, capabilities=caps)
    else:
        url = req.base_url or f"http://{req.device_id}"
        device = HTTPAdapter(req.device_id, url, capabilities=caps)
    result = _iot_layer.register_device(device)
    return {"success": result.success, "device_id": result.device_id, "reason": result.reason}


@app.get("/iot/devices", tags=["IoT"],
         dependencies=[Depends(sensor_access)])
async def list_iot_devices():
    if _iot_layer is None:
        return []
    return _iot_layer.list_devices()


@app.post("/iot/data/{device_id}", tags=["IoT"])
async def ingest_device_data(device_id: str, payload: dict):
    if _iot_layer is None:
        raise HTTPException(503, "IoT layer not initialized")
    raw = json.dumps(payload).encode()
    ok = _iot_layer.on_data(device_id, raw)
    if not ok:
        raise HTTPException(403, "Device not authenticated or unknown")
    return {"success": True}


@app.delete("/iot/devices/{device_id}", tags=["IoT"],
            dependencies=[Depends(admin_access)])
async def disconnect_device(device_id: str):
    if _iot_layer is None:
        raise HTTPException(503, "IoT layer not initialized")
    _iot_layer.on_disconnect(device_id)
    return {"success": True, "device_id": device_id}


# ==========================================
# CALIBRATION ENDPOINTS
# ==========================================

@app.post("/calibration/run", tags=["Calibration"],
          dependencies=[Depends(admin_access)])
async def run_calibration_endpoint(n: int = 30):
    """
    Collect n baseline readings, derive thresholds (mean±k·std),
    apply them to the engine, and persist to DB.
    Returns derived thresholds plus a validation check on a fresh reading.
    """
    import calibration as cal
    import sensor_reader

    if _brain is None:
        raise HTTPException(503, "Brain not initialised — calibration unavailable")

    result = cal.run_calibration(_brain.engine, n=n, reader=sensor_reader.read_all_sensors)

    if not result.get("success"):
        raise HTTPException(500, f"Calibration failed: {result.get('reason', 'unknown')}")

    # Validate a fresh reading for plausibility
    fresh = sensor_reader.read_all_sensors()
    validation = cal.validate_readings(fresh)

    return {
        "success": True,
        "thresholds": result["thresholds"],
        "validation": validation,
    }


@app.get("/calibration/status", tags=["Calibration"],
         dependencies=[Depends(sensor_access)])
async def get_calibration_status():
    """Return the most recent calibration result from the audit log."""
    import calibration as cal
    last = cal.load_calibration()
    return last or {"message": "No calibration performed yet"}


@app.post("/calibration/validate", tags=["Calibration"],
          dependencies=[Depends(sensor_access)])
async def validate_calibration():
    """
    Read sensors right now and check that all values are physically plausible.
    Does NOT re-derive thresholds — useful for a quick sanity check.
    """
    import calibration as cal
    import sensor_reader
    readings = sensor_reader.read_all_sensors()
    result = cal.validate_readings(readings)
    return result


# ==========================================
# TASK 12.5 — AUDIT ENDPOINTS
# ==========================================

@app.get("/audit/control", tags=["Audit"],
         dependencies=[Depends(admin_access)])
async def get_control_audit(limit: int = 100):
    conn = database.get_connection()
    try:
        rows = conn.execute("""
            SELECT * FROM audit_entries
            WHERE category IN ('control_dispatch','rejected_attempt','control_ack')
            ORDER BY timestamp DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.get("/audit/models", tags=["Audit"],
         dependencies=[Depends(admin_access)])
async def get_model_audit(limit: int = 100):
    conn = database.get_connection()
    try:
        rows = conn.execute("""
            SELECT * FROM audit_entries
            WHERE category IN ('model_promotion','recalibration','feedback_ingestion')
            ORDER BY timestamp DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ==========================================
# FEEDBACK ENDPOINT  (replaces AboutPage stub)
# ==========================================

class FeedbackRequest(BaseModel):
    name: str
    email: Optional[str] = None
    type: str = "general"
    message: str


@app.post("/feedback", tags=["Feedback"])
async def submit_feedback(req: FeedbackRequest):
    """
    Persist user-submitted feedback (name, email, type, message).
    Open endpoint — no auth required so unauthenticated visitors can submit.
    Feedback is written to the audit log so admins can review it.
    """
    if not req.name.strip():
        raise HTTPException(400, "name is required")
    if not req.message.strip():
        raise HTTPException(400, "message is required")

    obs_service.log_event(
        "feedback",
        "user_feedback",
        {
            "name": req.name.strip(),
            "email": (req.email or "").strip() or None,
            "type": req.type,
            "message": req.message.strip(),
        },
    )
    return {"success": True, "message": "Feedback received — thank you!"}


# ==========================================
# LEADERBOARD ENDPOINT  (backs TenderLeaderboard)
# ==========================================

# Baseline organisation records (industry-benchmarked; see TenderLeaderboard.jsx)
_LEADERBOARD_BASE = [
    {"rank": 1, "name": "Tata Steel Ltd.",              "abbr": "TSL",   "sector": "Steel Manufacturing",  "score": 88, "assets": 1240, "uptime": 98.7, "mtbf": 5200, "responseS": 4,  "badge": "🥇", "trend": "up"},
    {"rank": 2, "name": "Tech Mahindra Smart Infra",    "abbr": "TSI",   "sector": "Manufacturing",         "score": 81, "assets": 880,  "uptime": 97.9, "mtbf": 4100, "responseS": 7,  "badge": "🥈", "trend": "up"},
    {"rank": 3, "name": "Reliance Petrochemicals",      "abbr": "RPC",   "sector": "Petrochemical",         "score": 76, "assets": 760,  "uptime": 97.2, "mtbf": 3800, "responseS": 12, "badge": "🥉", "trend": "stable"},
    {"rank": 4, "name": "Indian Railways (Rolling Stock)","abbr": "IR-RS","sector": "Transport",            "score": 71, "assets": 2100, "uptime": 96.5, "mtbf": 2900, "responseS": 18, "badge": "🎖️", "trend": "up"},
    {"rank": 5, "name": "ONGC Offshore Platforms",      "abbr": "ONGC",  "sector": "Oil & Gas",            "score": 65, "assets": 430,  "uptime": 95.8, "mtbf": 2400, "responseS": 28, "badge": "🎖️", "trend": "down"},
    {"rank": 6, "name": "Siemens India Ltd.",           "abbr": "SIL",   "sector": "Industrial Automation", "score": 59, "assets": 320,  "uptime": 94.6, "mtbf": 2100, "responseS": 45, "badge": "",   "trend": "stable"},
    {"rank": 7, "name": "Larsen & Toubro Power",        "abbr": "L&T P", "sector": "Heavy Engineering",    "score": 52, "assets": 290,  "uptime": 93.1, "mtbf": 1750, "responseS": 72, "badge": "",   "trend": "up"},
]

# In-memory snapshot updated on each GET so clients see small live drift
# (matches the 8-second client-side simulation — now server-authoritative)
import random as _random
_leaderboard_state = [dict(o) for o in _LEADERBOARD_BASE]
_leaderboard_tick  = 0


def _tick_leaderboard():
    """Apply a tiny random walk to scores/uptime/mtbf/response, staying within ±3 of baseline."""
    global _leaderboard_tick
    _leaderboard_tick += 1
    for org, base in zip(_leaderboard_state, _LEADERBOARD_BASE):
        d_score    = (_random.random() - 0.5) * 0.4
        d_uptime   = (_random.random() - 0.5) * 0.04
        d_mtbf     = round((_random.random() - 0.5) * 20)
        d_response = (_random.random() - 0.5) * 0.5
        new_score  = round(max(base["score"] - 3, min(base["score"] + 3, org["score"] + d_score)))
        new_uptime = round(min(99.9, max(90.0, org["uptime"] + d_uptime)), 2)
        new_mtbf   = max(500, org["mtbf"] + d_mtbf)
        new_resp   = round(max(1.0, org["responseS"] + d_response), 1)
        org["score"]     = new_score
        org["uptime"]    = new_uptime
        org["mtbf"]      = new_mtbf
        org["responseS"] = new_resp
        org["trend"]     = "up" if new_score > org["score"] else ("down" if new_score < org["score"] else org["trend"])


@app.get("/leaderboard", tags=["Leaderboard"])
async def get_leaderboard():
    """
    Return the current industry-benchmarked leaderboard.
    Open endpoint — visible to unauthenticated visitors on the About/Leaderboard page.
    Data drifts slightly on each call to simulate live ranking changes.
    """
    _tick_leaderboard()
    return {
        "tick": _leaderboard_tick,
        "organisations": _leaderboard_state,
        "last_updated": time.time(),
    }
