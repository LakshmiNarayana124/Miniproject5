
# -*- coding: utf-8 -*-
"""
INTELLIWATCH — FastAPI Server

Handles:
- Authentication and role-protected sensor endpoints
- Hardware IoT ingestion and sensor streaming
- Control signals and status streaming
- ML and learning endpoints
- 3D explorer and history
- Equipment vision and object detection
- Calibration and audit
- Feedback and leaderboard

Hardware readings are accepted only through the validated IoT layer.
Simulation and Offline Demo remain separate frontend environments.
"""

import asyncio
import json
import os
import random as _random
import threading
import time

from copy import deepcopy
from typing import Optional, List

from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
    UploadFile,
    File,
    Form,
    Header,
    Query,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from auth import (
    auth_router,
    require_roles,
    get_current_user,
    initialize_auth_security,
)

from chatbot_api import router as chatbot_router

import database
import obs_service

from vision_service import (
    analyse_equipment_image_async,
    MAX_IMAGE_SIZE,
)

from equipment_detection_service import (
    detect_objects_async,
    MAX_FRAME_SIZE,
)


# ============================================================
# APPLICATION
# ============================================================

app = FastAPI(
    title="IntelliWatch – Real-Time Anomaly Detection",
    version="2.0.0",
)

_raw_origins = os.environ.get(
    "INTELLIWATCH_CORS_ORIGINS",
    "",
)

_extra_origins = [
    origin.strip()
    for origin in _raw_origins.split(",")
    if origin.strip()
]

_allowed_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
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
app.include_router(chatbot_router)


# ============================================================
# GLOBAL SINGLETONS
# ============================================================

_controller = None
_iot_layer = None
_learning_system = None
_brain = None

_status_clients: set = set()
_sensor_clients: list = []

_brain_lock = threading.Lock()

_assessment_lock = threading.Lock()
_latest_assessments = {}

try:
    SENSOR_STALE_SECONDS = max(
        3.0,
        float(
            os.environ.get(
                "INTELLIWATCH_SENSOR_STALE_SECONDS",
                "10",
            )
        ),
    )
except (TypeError, ValueError):
    SENSOR_STALE_SECONDS = 10.0


EXPECTED_SENSORS = (
    "vibration",
    "temperature",
    "current",
)

DEFAULT_SENSOR_UNITS = {
    "vibration": "g",
    "temperature": "°C",
    "current": "A",
}

VALID_SENSOR_QUALITIES = {
    "GOOD",
    "VALID",
    "WARNING",
    "DEGRADED",
}


# ============================================================
# HARDWARE SENSOR HELPERS
# ============================================================

def _unavailable_sensor_record(unit):
    return {
        "value": None,
        "unit": unit,
        "quality": "UNAVAILABLE",
        "metadata": {
            "source": "hardware",
        },
        "source": "hardware",
    }


def _get_hardware_snapshot():
    """
    Return the latest validated IoT hardware snapshot.

    A stale reading is not treated as a current reading.
    No synthetic or fallback values are generated here.
    """

    if _iot_layer is None:
        return None

    try:
        return _iot_layer.get_latest_sensor_snapshot(
            max_age_seconds=SENSOR_STALE_SECONDS,
        )
    except Exception:
        return None


def _get_snapshot_record(snapshot, sensor_key):
    """
    Return a sensor record while preserving its real value and unit.

    Missing, invalid, stale, or unavailable measurements are returned
    as None rather than being substituted with artificial values.
    """

    unit = DEFAULT_SENSOR_UNITS[sensor_key]

    if not isinstance(snapshot, dict):
        return _unavailable_sensor_record(unit)

    record = snapshot.get(sensor_key)

    if not isinstance(record, dict):
        return _unavailable_sensor_record(unit)

    value = record.get("value")
    quality = str(
        record.get("quality", "UNAVAILABLE")
    ).upper()

    if (
        value is None
        or quality not in VALID_SENSOR_QUALITIES
    ):
        result = _unavailable_sensor_record(
            record.get("unit") or unit
        )

        if quality in {"ERROR", "UNAVAILABLE"}:
            result["quality"] = quality

        return result

    metadata = record.get("metadata", {})

    if not isinstance(metadata, dict):
        metadata = {}

    result = deepcopy(record)

    result["value"] = float(value)
    result["unit"] = record.get("unit") or unit
    result["quality"] = quality
    result["metadata"] = deepcopy(metadata)
    result["metadata"]["source"] = "hardware"
    result["source"] = "hardware"

    return result


def _build_sensor_stream_payload(snapshot):
    """Build the frontend-compatible sensor streaming payload."""

    now_ms = int(time.time() * 1000)

    if snapshot:
        try:
            timestamp_ms = int(
                float(snapshot.get("timestamp", time.time())) * 1000
            )
        except (TypeError, ValueError):
            timestamp_ms = now_ms

        device_id = snapshot.get("device_id")
        status_value = "ok"
    else:
        timestamp_ms = now_ms
        device_id = None
        status_value = "unavailable"

    records = {
        key: _get_snapshot_record(snapshot, key)
        for key in EXPECTED_SENSORS
    }

    if not any(
        record.get("value") is not None
        for record in records.values()
    ):
        status_value = "unavailable"

    payload = {
        "ts": timestamp_ms,
        "timestamp": timestamp_ms / 1000,
        "source": "hardware",
        "device_id": device_id,
        "status": status_value,
        "vibration": records["vibration"],
        "temperature": records["temperature"],
        "current": records["current"],
    }

    return payload


def _unavailable_assessment(message=None):
    """Structured unavailable response when no assessment exists."""

    return {
        "success": False,
        "message": message or (
            "Awaiting valid hardware sensor readings. "
            "No synthetic values were substituted."
        ),
        "sensor_readings_saved": 0,
        "sensor_statuses": {
            "vibration": "UNAVAILABLE",
            "temperature": "UNAVAILABLE",
            "current": "UNAVAILABLE",
        },
        "overall_system_status": "UNAVAILABLE",
    }


# ============================================================
# IOT-TO-BRAIN INFERENCE CALLBACK
# ============================================================

def _handle_iot_inference_payload(device_id, raw_payload):
    """
    Process a validated hardware payload exactly once after ingestion.
    """

    if _brain is None:
        return

    try:
        if not isinstance(raw_payload, bytes):
            raise ValueError(
                "IoT payload must be bytes."
            )

        decoded = json.loads(
            raw_payload.decode("utf-8")
        )

        if not isinstance(decoded, dict):
            raise ValueError(
                "IoT payload must contain a JSON object."
            )

        source_readings = decoded.get(
            "readings",
            decoded,
        )

        if not isinstance(source_readings, dict):
            raise ValueError(
                "Sensor readings must be a JSON object."
            )

        readings = {}

        for sensor_key in EXPECTED_SENSORS:
            record = source_readings.get(sensor_key)

            if not isinstance(record, dict):
                continue

            clean_record = deepcopy(record)

            metadata = clean_record.get(
                "metadata",
                {},
            )

            if not isinstance(metadata, dict):
                metadata = {}

            metadata["source"] = "hardware"

            clean_record["metadata"] = metadata
            clean_record["source"] = "hardware"

            readings[sensor_key] = clean_record

        if not readings:
            raise ValueError(
                "No recognised sensor records were received."
            )

        with _brain_lock:
            result = _brain.run_cycle(
                mode="automatic",
                readings=readings,
            )

        with _assessment_lock:
            _latest_assessments[device_id] = {
                "processed_at": time.time(),
                "result": result,
            }

        logger_message = (
            result.get("overall_system_status", "UNKNOWN")
            if isinstance(result, dict)
            else "UNKNOWN"
        )

        print(
            f"[IoT] Brain processed hardware snapshot "
            f"from '{device_id}': {logger_message}"
        )

        # Act on the detected anomaly, not merely read it: map the brain's
        # system status to a control signal and dispatch it so the relays and
        # LCD respond automatically. Only dispatch on status *change* (dedup
        # via the controller's latched status) to avoid re-firing every
        # snapshot. A system session authorises SHUTDOWN / DE_RATE.
        if (
            _controller is not None
            and logger_message in ("NORMAL", "WARNING", "CRITICAL")
            and logger_message != _controller.latched_status
        ):
            try:
                _controller.on_status(
                    logger_message,
                    trace=result,
                    session={
                        "role": "MAINTENANCE_ENGINEER",
                        "username": "system-auto-actuation",
                    },
                )
            except Exception as act_error:
                print(
                    f"[IoT] Auto-actuation failed for "
                    f"'{device_id}': {act_error}"
                )

    except Exception as error:
        print(
            f"[IoT] Brain processing failed for "
            f"'{device_id}': {error}"
        )


# ============================================================
# WEBSOCKET AUTHENTICATION
# ============================================================

WEBSOCKET_ALLOWED_ROLES = {
    "ADMIN",
    "OPERATOR",
    "MAINTENANCE_ENGINEER",
}


async def _authenticate_websocket(websocket):
    token = websocket.query_params.get("token")

    if not token:
        await websocket.close(
            code=1008,
            reason="Authentication required",
        )
        return None

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=token,
    )

    try:
        user = await get_current_user(credentials)

    except HTTPException:
        await websocket.close(
            code=1008,
            reason="Invalid or expired authentication token",
        )
        return None

    except Exception:
        await websocket.close(
            code=1011,
            reason="Authentication service unavailable",
        )
        return None

    if user.get("role") not in WEBSOCKET_ALLOWED_ROLES:
        await websocket.close(
            code=1008,
            reason="Insufficient permissions",
        )
        return None

    return user


# ============================================================
# STARTUP / SHUTDOWN
# ============================================================

@app.on_event("startup")
async def startup():
    global _controller
    global _iot_layer
    global _learning_system
    global _brain

    database.initialize_database()
    initialize_auth_security()

    print(
        "[startup] Authentication security storage ready"
    )

    try:
        from intelliwatch_brain import IntelliWatchBrain

        _brain = IntelliWatchBrain(
            auto_calibrate=False,
        )

        print("[startup] IntelliWatchBrain ready")

    except Exception as error:
        print(
            f"[startup] IntelliWatchBrain init warning: {error}"
        )

    try:
        from iot_layer import IoTIntegrationLayer

        _iot_layer = IoTIntegrationLayer(
            inference_callback=_handle_iot_inference_payload,
        )

        _iot_layer.start_heartbeat()

        print(
            "[startup] IoTIntegrationLayer ready "
            "with hardware inference callback"
        )

    except Exception as error:
        print(
            f"[startup] IoT layer init warning: {error}"
        )

    try:
        from equipment_controller import EquipmentController

        _controller = EquipmentController(
            iot_layer=_iot_layer
        )

        _controller.add_alert_listener(
            _broadcast_alert
        )

    except Exception as error:
        print(
            f"[startup] EquipmentController init warning: {error}"
        )

    try:
        from lcd_relay_module import (
            LCDRelayEdgeAdapter,
            create_lcd_relay_actuator,
        )

        # Flow 2 (app -> hardware): register the LCD + relay actuator as an
        # HTTP edge device and authenticate it so EquipmentController
        # dispatches reach the physical relays and display via relay().
        _lcd_relay_adapter = LCDRelayEdgeAdapter(
            device_id="lcd-relay-01",
            actuator=create_lcd_relay_actuator(),
        )

        _lcd_handshake = _iot_layer.register_device(
            _lcd_relay_adapter
        )

        if not _lcd_handshake.success:
            print(
                f"[startup] LCD+relay actuator registration failed: "
                f"{_lcd_handshake.reason}"
            )
        else:
            _iot_layer.authenticate(
                _lcd_handshake.device_id,
                _lcd_handshake.device_credential,
            )
            print(
                "[startup] LCD+relay actuator registered & "
                "authenticated (app->hardware control flow ready)"
            )
    except Exception as error:
        print(
            f"[startup] LCD+relay actuator init warning: {error}"
        )

    try:
        from learning_system import LearningSystem

        _learning_system = LearningSystem()

    except Exception as error:
        print(
            f"[startup] LearningSystem init warning: {error}"
        )

    try:
        from explorer_ml import train_explorer_model
        from model_registry import registry

        if registry.active_model("explorer") is None:
            train_explorer_model()

    except Exception as error:
        print(
            f"[startup] Explorer model init warning: {error}"
        )

    try:
        obs_service.check_model_degradation()
    except Exception as error:
        print(
            f"[startup] Model degradation check warning: {error}"
        )


@app.on_event("shutdown")
async def shutdown():
    if _iot_layer:
        try:
            _iot_layer.stop_heartbeat()
        except Exception:
            pass

    for ws in list(_sensor_clients):
        try:
            await ws.close()
        except Exception:
            pass

    for ws in list(_status_clients):
        try:
            await ws.close()
        except Exception:
            pass


# ============================================================
# STATUS BROADCAST
# ============================================================

def _broadcast_alert(alert):
    msg = json.dumps(
        alert,
        default=str,
    )

    async def _send_all():
        for ws in list(_status_clients):
            try:
                await ws.send_text(msg)
            except Exception:
                _status_clients.discard(ws)

    try:
        loop = asyncio.get_event_loop()

        if loop.is_running():
            asyncio.run_coroutine_threadsafe(
                _send_all(),
                loop,
            )

    except Exception:
        pass


# ============================================================
# PERMISSIONS
# ============================================================

sensor_access = require_roles(
    "ADMIN",
    "OPERATOR",
    "MAINTENANCE_ENGINEER",
)

admin_access = require_roles("ADMIN")

actuation_access = require_roles(
    "ADMIN",
    "MAINTENANCE_ENGINEER",
)

operator_access = require_roles(
    "OPERATOR",
    "MAINTENANCE_ENGINEER",
)

label_access = require_roles(
    "ADMIN",
    "OPERATOR",
    "MAINTENANCE_ENGINEER",
)


# ============================================================
# EQUIPMENT VISION — IMAGE ANALYSIS
# ============================================================

@app.post(
    "/vision/analyse",
    tags=["Vision"],
)
async def analyse_equipment(
    image: UploadFile = File(...),
    language: str = Form(default="en"),
    user=Depends(sensor_access),
):
    """
    Analyse one manually captured equipment image.

    Supported languages:
        en - English
        hi - Hindi
        kn - Kannada
        ta - Tamil
        te - Telugu
    """

    allowed_types = {
        "image/jpeg",
        "image/png",
        "image/webp",
    }

    supported_languages = {
        "en",
        "hi",
        "kn",
        "ta",
        "te",
    }

    language = str(language).strip().lower()

    if language not in supported_languages:
        await image.close()

        raise HTTPException(
            status_code=422,
            detail=(
                "Unsupported language. "
                "Use en, hi, kn, ta or te."
            ),
        )

    if image.content_type not in allowed_types:
        await image.close()

        raise HTTPException(
            status_code=415,
            detail="Only JPEG, PNG and WEBP images are supported.",
        )

    try:
        image_bytes = await image.read(
            MAX_IMAGE_SIZE + 1
        )

        if not image_bytes:
            raise HTTPException(
                status_code=400,
                detail="The uploaded image is empty.",
            )

        if len(image_bytes) > MAX_IMAGE_SIZE:
            raise HTTPException(
                status_code=413,
                detail="Image exceeds the 8 MB limit.",
            )

        result = await analyse_equipment_image_async(
            image_bytes,
            image.content_type,
            language,
        )

        return {
            "success": True,
            "analysis": result,
        }

    except HTTPException:
        raise

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except RuntimeError:
        raise HTTPException(
            status_code=503,
            detail="Equipment analysis service is unavailable.",
        )

    except Exception:
        raise HTTPException(
            status_code=502,
            detail="Equipment image analysis failed. Please try again.",
        )

    finally:
        await image.close()


# ============================================================
# EQUIPMENT VISION — LIVE OBJECT DETECTION
# ============================================================

@app.post(
    "/vision/detect",
    tags=["Vision"],
)
async def detect_equipment_frame(
    image: UploadFile = File(...),
    user=Depends(sensor_access),
):
    allowed_types = {
        "image/jpeg",
        "image/png",
        "image/webp",
    }

    if image.content_type not in allowed_types:
        await image.close()

        raise HTTPException(
            status_code=415,
            detail="Only JPEG, PNG and WEBP images are supported.",
        )

    try:
        image_bytes = await image.read(
            MAX_FRAME_SIZE + 1
        )

        if not image_bytes:
            raise HTTPException(
                status_code=400,
                detail="The uploaded frame is empty.",
            )

        if len(image_bytes) > MAX_FRAME_SIZE:
            raise HTTPException(
                status_code=413,
                detail="Frame exceeds the 2 MB limit.",
            )

        result = await detect_objects_async(
            image_bytes,
            image.content_type,
        )

        return {
            "success": True,
            "detection": result,
        }

    except HTTPException:
        raise

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except RuntimeError:
        raise HTTPException(
            status_code=503,
            detail="Equipment detection service is unavailable.",
        )

    except Exception:
        raise HTTPException(
            status_code=502,
            detail="Equipment detection failed. Please try again.",
        )

    finally:
        await image.close()


# ============================================================
# SENSOR RESPONSE MODELS
# ============================================================

class VibrationData(BaseModel):
    x_g: Optional[float] = None
    y_g: Optional[float] = None
    z_g: Optional[float] = None
    magnitude_g: Optional[float] = None
    quality: str = "UNAVAILABLE"


class TemperatureData(BaseModel):
    celsius: Optional[float] = None
    fahrenheit: Optional[float] = None
    quality: str = "UNAVAILABLE"


class CurrentData(BaseModel):
    rms_current_a: Optional[float] = None
    dc_current_a: Optional[float] = None
    raw_voltage_v: Optional[float] = None
    quality: str = "UNAVAILABLE"


# ============================================================
# HEALTH
# ============================================================

@app.get("/", tags=["Health"])
async def root():
    return {
        "project": "IntelliWatch",
        "status": "running",
        "version": "2.0.0",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "ok",
        "timestamp": time.time(),
    }


# ============================================================
# SENSOR ENDPOINTS
# ============================================================

@app.get(
    "/sensors/vibration",
    response_model=VibrationData,
    tags=["Sensors"],
    dependencies=[Depends(sensor_access)],
)
async def get_vibration():
    snapshot = _get_hardware_snapshot()

    record = _get_snapshot_record(
        snapshot,
        "vibration",
    )

    metadata = record.get("metadata", {})

    return VibrationData(
        x_g=metadata.get("x"),
        y_g=metadata.get("y"),
        z_g=metadata.get("z"),
        magnitude_g=record.get("value"),
        quality=record.get("quality", "UNAVAILABLE"),
    )


@app.get(
    "/sensors/temperature",
    response_model=TemperatureData,
    tags=["Sensors"],
    dependencies=[Depends(sensor_access)],
)
async def get_temperature():
    snapshot = _get_hardware_snapshot()

    record = _get_snapshot_record(
        snapshot,
        "temperature",
    )

    celsius = record.get("value")

    fahrenheit = (
        celsius * 9 / 5 + 32
        if celsius is not None
        else None
    )

    return TemperatureData(
        celsius=celsius,
        fahrenheit=fahrenheit,
        quality=record.get("quality", "UNAVAILABLE"),
    )


@app.get(
    "/sensors/current",
    response_model=CurrentData,
    tags=["Sensors"],
    dependencies=[Depends(sensor_access)],
)
async def get_current():
    snapshot = _get_hardware_snapshot()

    record = _get_snapshot_record(
        snapshot,
        "current",
    )

    metadata = record.get("metadata", {})

    dc_current = metadata.get("dc_current_a")
    raw_voltage = metadata.get("raw_voltage_v")

    return CurrentData(
        rms_current_a=record.get("value"),
        dc_current_a=dc_current,
        raw_voltage_v=raw_voltage,
        quality=record.get("quality", "UNAVAILABLE"),
    )


@app.get(
    "/sensors/all",
    tags=["Sensors"],
    dependencies=[Depends(sensor_access)],
)
async def get_all_sensors():
    snapshot = _get_hardware_snapshot()

    records = {
        key: _get_snapshot_record(snapshot, key)
        for key in EXPECTED_SENSORS
    }

    assessment = None

    if snapshot:
        device_id = snapshot.get("device_id")

        with _assessment_lock:
            cached = _latest_assessments.get(device_id)

            if cached:
                assessment = deepcopy(
                    cached.get("result")
                )

    if assessment is None:
        assessment = _unavailable_assessment()

    any_valid_reading = any(
        record.get("value") is not None
        for record in records.values()
    )

    return {
        "timestamp": (
            snapshot.get("timestamp")
            if snapshot
            else time.time()
        ),
        "source": "hardware",
        "device_id": (
            snapshot.get("device_id")
            if snapshot
            else None
        ),
        "status": (
            "ok"
            if any_valid_reading
            else "unavailable"
        ),
        "vibration": records["vibration"],
        "temperature": records["temperature"],
        "current": records["current"],
        "assessment": assessment,
    }


# ============================================================
# SENSOR WEBSOCKET
# ============================================================

@app.websocket("/stream/sensors")
async def sensor_stream(websocket: WebSocket):
    user = await _authenticate_websocket(websocket)

    if user is None:
        return

    await websocket.accept()
    _sensor_clients.append(websocket)

    try:
        while True:
            snapshot = _get_hardware_snapshot()

            payload = _build_sensor_stream_payload(
                snapshot
            )

            await websocket.send_text(
                json.dumps(
                    payload,
                    default=str,
                    allow_nan=False,
                )
            )

            await asyncio.sleep(3)

    except WebSocketDisconnect:
        pass

    except Exception as error:
        print(
            f"[WebSocket] Sensor stream error: {error}"
        )

    finally:
        if websocket in _sensor_clients:
            _sensor_clients.remove(websocket)


# ============================================================
# TASK 12.1 — CONTROL / STATUS ENDPOINTS
# ============================================================

class DispatchRequest(BaseModel):
    intent: str
    target_equipment: Optional[str] = "default"


class AckRequest(BaseModel):
    control_signal_id: int
    equipment_state: str = ""


@app.post(
    "/control/dispatch",
    tags=["Control"],
    dependencies=[Depends(actuation_access)],
)
async def dispatch_control(
    req: DispatchRequest,
    user=Depends(actuation_access),
):
    if _controller is None:
        raise HTTPException(
            503,
            "Controller not initialized",
        )

    from equipment_controller import PermissionDenied

    try:
        result = _controller.dispatch(
            intent=req.intent.upper(),
            status=obs_service._current_status.get(
                "status",
                "NORMAL",
            ),
            session={
                "role": user["role"],
                "username": user["username"],
            },
            target_equipment=req.target_equipment,
        )

        obs_service.set_current_status(
            result["status"],
            result["intent"],
        )

        await _push_status_update()

        return result

    except PermissionDenied as error:
        raise HTTPException(
            403,
            str(error),
        )


@app.get(
    "/control/current",
    tags=["Control"],
    dependencies=[Depends(sensor_access)],
)
async def get_current_control():
    return obs_service.get_system_status(
        _iot_layer
    )


@app.post(
    "/control/ack",
    tags=["Control"],
    dependencies=[Depends(actuation_access)],
)
async def ack_control(req: AckRequest):
    if _controller is None:
        raise HTTPException(
            503,
            "Controller not initialized",
        )

    ok = _controller.on_ack(
        req.control_signal_id,
        req.equipment_state,
    )

    return {
        "acknowledged": ok,
        "control_signal_id": req.control_signal_id,
    }


# ============================================================
# STATUS WEBSOCKET
# ============================================================

@app.websocket("/stream/status")
async def status_stream(websocket: WebSocket):
    user = await _authenticate_websocket(websocket)

    if user is None:
        return

    await websocket.accept()
    _status_clients.add(websocket)

    try:
        await websocket.send_text(
            json.dumps(
                obs_service.get_system_status(_iot_layer),
                default=str,
            )
        )

        while True:
            await asyncio.sleep(5)

            await websocket.send_text(
                json.dumps(
                    obs_service.get_system_status(_iot_layer),
                    default=str,
                )
            )

    except WebSocketDisconnect:
        pass

    except Exception as error:
        print(
            f"[WebSocket] Status stream error: {error}"
        )

    finally:
        _status_clients.discard(websocket)


async def _push_status_update():
    msg = json.dumps(
        obs_service.get_system_status(_iot_layer),
        default=str,
    )

    for ws in list(_status_clients):
        try:
            await ws.send_text(msg)
        except Exception:
            _status_clients.discard(ws)


# ============================================================
# TASK 12.2 — MODEL / LEARNING ENDPOINTS
# ============================================================

@app.get(
    "/models/status",
    tags=["Models"],
    dependencies=[Depends(sensor_access)],
)
async def get_models_status():
    return obs_service.get_all_model_statuses()


@app.get(
    "/models/trend/{family}",
    tags=["Models"],
    dependencies=[Depends(sensor_access)],
)
async def get_model_trend(family: str):
    return {
        "family": family,
        "trend": obs_service.get_accuracy_trend(family),
    }


@app.get(
    "/models/degradation",
    tags=["Models"],
    dependencies=[Depends(sensor_access)],
)
async def get_degradation():
    return {
        "alerts": obs_service.check_model_degradation(),
    }


class LabelRequest(BaseModel):
    event_id: Optional[int] = None
    label: str
    feature_vector: list
    model_version: str


class RecalibrateRequest(BaseModel):
    family: str = "tabular"


@app.post(
    "/learning/label",
    tags=["Learning"],
    dependencies=[Depends(label_access)],
)
async def submit_label(
    req: LabelRequest,
    user=Depends(label_access),
):
    if _learning_system is None:
        raise HTTPException(
            503,
            "Learning system not initialized",
        )

    row_id = _learning_system.submit_label(
        event_id=req.event_id,
        label=req.label,
        feature_vector=req.feature_vector,
        model_version=req.model_version,
        verified_by=user["username"],
    )

    obs_service.log_event(
        "feedback_ingestion",
        "label_submitted",
        {"row_id": row_id},
    )

    return {
        "success": True,
        "label_id": row_id,
    }


@app.post(
    "/learning/recalibrate",
    tags=["Learning"],
    dependencies=[Depends(admin_access)],
)
async def trigger_recalibrate(req: RecalibrateRequest):
    if _learning_system is None:
        raise HTTPException(
            503,
            "Learning system not initialized",
        )

    result = _learning_system.recalibrate(
        family=req.family,
    )

    obs_service.log_event(
        "recalibration",
        "completed",
        result,
    )

    return result


# ============================================================
# TASK 12.3 — 3D EXPLORER ENDPOINTS
# ============================================================

class ExplorerClassifyRequest(BaseModel):
    arrangement: list = Field(default_factory=list)
    readings: dict = Field(default_factory=dict)


class ExplorerHistoryRequest(BaseModel):
    entry_type: str
    active_user: Optional[str] = None
    arrangement: Optional[list] = None
    classification_label: Optional[str] = None
    confidence: Optional[float] = None
    model_version: Optional[str] = None


@app.post(
    "/explorer/classify",
    tags=["Explorer"],
    dependencies=[Depends(sensor_access)],
)
async def explorer_classify(req: ExplorerClassifyRequest):
    from explorer_ml import classify

    return classify(
        req.arrangement,
        req.readings,
    )


@app.post(
    "/explorer/history",
    tags=["Explorer"],
    dependencies=[Depends(sensor_access)],
)
async def add_explorer_history(req: ExplorerHistoryRequest):
    arr_json = (
        json.dumps(req.arrangement)
        if req.arrangement is not None
        else None
    )

    row_id = database.save_explorer_history_entry(
        entry_type=req.entry_type,
        active_user=req.active_user,
        arrangement_json=arr_json,
        classification_label=req.classification_label,
        confidence=req.confidence,
        model_version=req.model_version,
    )

    return {
        "success": True,
        "id": row_id,
    }


@app.get(
    "/explorer/history",
    tags=["Explorer"],
    dependencies=[Depends(sensor_access)],
)
async def list_explorer_history(limit: int = 50):
    return database.get_explorer_history(limit)


@app.get(
    "/explorer/history/{entry_id}",
    tags=["Explorer"],
    dependencies=[Depends(sensor_access)],
)
async def get_explorer_history_entry(entry_id: int):
    entry = database.get_explorer_history_entry(
        entry_id
    )

    if not entry:
        raise HTTPException(
            404,
            "History entry not found",
        )

    return entry


# ============================================================
# TASK 12.4 — IOT ENDPOINTS
# ============================================================

class DeviceRegisterRequest(BaseModel):
    device_id: str = Field(
        min_length=1,
        max_length=128,
    )

    protocol: str = "HTTP"

    capabilities: List[str] = Field(
        default_factory=list,
    )

    base_url: Optional[str] = None
    broker_host: Optional[str] = None

    credential: Optional[str] = Field(
        default=None,
        min_length=32,
        max_length=256,
    )


@app.post(
    "/iot/devices",
    tags=["IoT"],
    dependencies=[Depends(admin_access)],
)
async def register_iot_device(req: DeviceRegisterRequest):
    if _iot_layer is None:
        raise HTTPException(
            503,
            "IoT layer not initialized",
        )

    from iot_layer import (
        HTTPAdapter,
        MQTTAdapter,
    )

    protocol = req.protocol.upper()
    capabilities = set(req.capabilities)

    if protocol == "MQTT":
        if not req.broker_host:
            raise HTTPException(
                400,
                "broker_host is required for MQTT registration.",
            )

        device = MQTTAdapter(
            req.device_id,
            req.broker_host,
            capabilities=capabilities,
        )

    elif protocol == "HTTP":
        if not req.base_url:
            raise HTTPException(
                400,
                "base_url is required for HTTP registration.",
            )

        device = HTTPAdapter(
            req.device_id,
            req.base_url,
            capabilities=capabilities,
        )

    else:
        raise HTTPException(
            400,
            "Unsupported IoT protocol. Use HTTP or MQTT.",
        )

    result = _iot_layer.register_device(
        device,
        credential=req.credential,
    )

    if not result.success:
        raise HTTPException(
            400,
            detail=result.reason or "Device registration failed.",
        )

    return {
        "success": True,
        "device_id": result.device_id,
        "protocol": result.protocol,
        "capabilities": sorted(result.capabilities),
        "credential_configured": bool(
            result.device_credential
        ),
        "device_credential": result.device_credential,
        "credential_note": (
            "Store this credential securely on the edge device. "
            "The server keeps its active copy in memory; after a "
            "server restart, register and provision the device again."
        ),
    }


@app.get(
    "/iot/devices",
    tags=["IoT"],
    dependencies=[Depends(sensor_access)],
)
async def list_iot_devices():
    if _iot_layer is None:
        return []

    return _iot_layer.list_devices()


@app.post(
    "/iot/data/{device_id}",
    tags=["IoT"],
)
async def ingest_device_data(
    device_id: str,
    payload: dict,
    device_credential: Optional[str] = Header(
        default=None,
        alias="X-Device-Credential",
    ),
):
    if _iot_layer is None:
        raise HTTPException(
            503,
            "IoT layer not initialized",
        )

    if not device_credential:
        raise HTTPException(
            401,
            "X-Device-Credential header is required.",
        )

    try:
        raw_payload = json.dumps(
            payload,
            allow_nan=False,
        ).encode("utf-8")

    except (TypeError, ValueError):
        raise HTTPException(
            400,
            "Payload must contain valid JSON-compatible values.",
        )

    if len(raw_payload) > 64 * 1024:
        raise HTTPException(
            413,
            "Sensor payload exceeds the 64 KB limit.",
        )

    ok = _iot_layer.on_data(
        device_id,
        raw_payload,
        credential=device_credential,
    )

    if not ok:
        raise HTTPException(
            401,
            "Device authentication failed or sensor payload was rejected.",
        )

    return {
        "success": True,
        "device_id": device_id,
        "source": "hardware",
        "message": "Validated hardware readings accepted.",
    }


@app.delete(
    "/iot/devices/{device_id}",
    tags=["IoT"],
    dependencies=[Depends(admin_access)],
)
async def disconnect_device(device_id: str):
    if _iot_layer is None:
        raise HTTPException(
            503,
            "IoT layer not initialized",
        )

    _iot_layer.on_disconnect(device_id)

    return {
        "success": True,
        "device_id": device_id,
    }


# ============================================================
# CALIBRATION HELPERS
# ============================================================

def _make_iot_calibration_reader():
    """
    Create a reader that waits for a new hardware snapshot.
    """

    last_timestamp = [None]

    def reader():
        deadline = (
            time.monotonic()
            + max(10.0, SENSOR_STALE_SECONDS * 2)
        )

        while time.monotonic() < deadline:
            snapshot = _get_hardware_snapshot()

            if snapshot:
                sample_timestamp = snapshot.get(
                    "timestamp"
                )

                if (
                    sample_timestamp is not None
                    and sample_timestamp != last_timestamp[0]
                ):
                    last_timestamp[0] = sample_timestamp

                    readings = {}

                    for sensor_key in EXPECTED_SENSORS:
                        record = snapshot.get(sensor_key)

                        if isinstance(record, dict):
                            readings[sensor_key] = deepcopy(record)

                    return readings

            time.sleep(0.1)

        raise RuntimeError(
            "Timed out waiting for a new hardware sensor snapshot."
        )

    return reader


# ============================================================
# CALIBRATION ENDPOINTS
# ============================================================

@app.post(
    "/calibration/run",
    tags=["Calibration"],
    dependencies=[Depends(admin_access)],
)
async def run_calibration_endpoint(
    n: int = Query(default=30, ge=30, le=500),
):
    import calibration as cal

    if _brain is None:
        raise HTTPException(
            503,
            "Brain not initialized — calibration unavailable.",
        )

    if _get_hardware_snapshot() is None:
        raise HTTPException(
            503,
            "No recent hardware readings are available. "
            "Connect the IoT device before calibration.",
        )

    reader = _make_iot_calibration_reader()

    try:
        result = await asyncio.to_thread(
            cal.run_calibration,
            _brain.engine,
            n=n,
            reader=reader,
        )

    except RuntimeError as error:
        raise HTTPException(
            503,
            f"Hardware calibration could not collect fresh samples: {error}",
        )

    except Exception:
        raise HTTPException(
            500,
            "Hardware calibration failed.",
        )

    if not result.get("success"):
        raise HTTPException(
            500,
            f"Calibration failed: {result.get('reason', 'unknown')}",
        )

    fresh = _get_hardware_snapshot()

    if fresh is None:
        validation = {
            "passed": False,
            "message": "No recent hardware readings available for validation.",
        }

    else:
        readings = {
            key: deepcopy(fresh[key])
            for key in EXPECTED_SENSORS
            if isinstance(fresh.get(key), dict)
        }

        validation = cal.validate_readings(
            readings
        )

    return {
        "success": True,
        "source": "hardware",
        "thresholds": result["thresholds"],
        "validation": validation,
    }


@app.get(
    "/calibration/status",
    tags=["Calibration"],
    dependencies=[Depends(sensor_access)],
)
async def get_calibration_status():
    import calibration as cal

    last = cal.load_calibration(
        source="hardware"
    )

    return last or {
        "message": "No hardware calibration performed yet.",
        "source": "hardware",
    }


@app.post(
    "/calibration/validate",
    tags=["Calibration"],
    dependencies=[Depends(sensor_access)],
)
async def validate_calibration():
    import calibration as cal

    snapshot = _get_hardware_snapshot()

    if snapshot is None:
        raise HTTPException(
            503,
            "No recent hardware readings are available.",
        )

    readings = {
        key: deepcopy(snapshot[key])
        for key in EXPECTED_SENSORS
        if isinstance(snapshot.get(key), dict)
    }

    return cal.validate_readings(
        readings
    )


# ============================================================
# TASK 12.5 — AUDIT ENDPOINTS
# ============================================================

@app.get(
    "/audit/control",
    tags=["Audit"],
    dependencies=[Depends(admin_access)],
)
async def get_control_audit(limit: int = 100):
    limit = max(1, min(limit, 1000))

    conn = database.get_connection()

    try:
        rows = conn.execute(
            """
            SELECT * FROM audit_entries
            WHERE category IN (
                'control_dispatch',
                'rejected_attempt',
                'control_ack'
            )
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:
        conn.close()


@app.get(
    "/audit/models",
    tags=["Audit"],
    dependencies=[Depends(admin_access)],
)
async def get_model_audit(limit: int = 100):
    limit = max(1, min(limit, 1000))

    conn = database.get_connection()

    try:
        rows = conn.execute(
            """
            SELECT * FROM audit_entries
            WHERE category IN (
                'model_promotion',
                'recalibration',
                'feedback_ingestion'
            )
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:
        conn.close()


# ============================================================
# FEEDBACK ENDPOINT
# ============================================================

class FeedbackRequest(BaseModel):
    name: str
    email: Optional[str] = None
    type: str = "general"
    message: str


@app.post(
    "/feedback",
    tags=["Feedback"],
)
async def submit_feedback(req: FeedbackRequest):
    if not req.name.strip():
        raise HTTPException(
            400,
            "name is required",
        )

    if not req.message.strip():
        raise HTTPException(
            400,
            "message is required",
        )

    obs_service.log_event(
        "feedback",
        "user_feedback",
        {
            "name": req.name.strip(),
            "email": (
                (req.email or "").strip() or None
            ),
            "type": req.type,
            "message": req.message.strip(),
        },
    )

    return {
        "success": True,
        "message": "Feedback received — thank you!",
    }


# ============================================================
# LEADERBOARD ENDPOINT
# ============================================================

_LEADERBOARD_BASE = [
    {
        "rank": 1,
        "name": "Tata Steel Ltd.",
        "abbr": "TSL",
        "sector": "Steel Manufacturing",
        "score": 88,
        "assets": 1240,
        "uptime": 98.7,
        "mtbf": 5200,
        "responseS": 4,
        "badge": "🥇",
        "trend": "up",
    },
    {
        "rank": 2,
        "name": "Tech Mahindra Smart Infra",
        "abbr": "TSI",
        "sector": "Manufacturing",
        "score": 81,
        "assets": 880,
        "uptime": 97.9,
        "mtbf": 4100,
        "responseS": 7,
        "badge": "🥈",
        "trend": "up",
    },
    {
        "rank": 3,
        "name": "Reliance Petrochemicals",
        "abbr": "RPC",
        "sector": "Petrochemical",
        "score": 76,
        "assets": 760,
        "uptime": 97.2,
        "mtbf": 3800,
        "responseS": 12,
        "badge": "🥉",
        "trend": "stable",
    },
    {
        "rank": 4,
        "name": "Indian Railways (Rolling Stock)",
        "abbr": "IR-RS",
        "sector": "Transport",
        "score": 71,
        "assets": 2100,
        "uptime": 96.5,
        "mtbf": 2900,
        "responseS": 18,
        "badge": "🎖️",
        "trend": "up",
    },
    {
        "rank": 5,
        "name": "ONGC Offshore Platforms",
        "abbr": "ONGC",
        "sector": "Oil & Gas",
        "score": 65,
        "assets": 430,
        "uptime": 95.8,
        "mtbf": 2400,
        "responseS": 28,
        "badge": "🎖️",
        "trend": "down",
    },
    {
        "rank": 6,
        "name": "Siemens India Ltd.",
        "abbr": "SIL",
        "sector": "Industrial Automation",
        "score": 59,
        "assets": 320,
        "uptime": 94.6,
        "mtbf": 2100,
        "responseS": 45,
        "badge": "",
        "trend": "stable",
    },
    {
        "rank": 7,
        "name": "Larsen & Toubro Power",
        "abbr": "L&T P",
        "sector": "Heavy Engineering",
        "score": 52,
        "assets": 290,
        "uptime": 93.1,
        "mtbf": 1750,
        "responseS": 72,
        "badge": "",
        "trend": "up",
    },
]

_leaderboard_state = [
    dict(org)
    for org in _LEADERBOARD_BASE
]

_leaderboard_tick = 0


def _tick_leaderboard():
    global _leaderboard_tick

    _leaderboard_tick += 1

    for org, base in zip(
        _leaderboard_state,
        _LEADERBOARD_BASE,
    ):
        d_score = (
            (_random.random() - 0.5) * 0.4
        )

        d_uptime = (
            (_random.random() - 0.5) * 0.04
        )

        d_mtbf = round(
            (_random.random() - 0.5) * 20
        )

        d_response = (
            (_random.random() - 0.5) * 0.5
        )

        old_score = org["score"]

        new_score = round(
            max(
                base["score"] - 3,
                min(
                    base["score"] + 3,
                    old_score + d_score,
                ),
            )
        )

        new_uptime = round(
            min(
                99.9,
                max(
                    90.0,
                    org["uptime"] + d_uptime,
                ),
            ),
            2,
        )

        new_mtbf = max(
            500,
            org["mtbf"] + d_mtbf,
        )

        new_resp = round(
            max(
                1.0,
                org["responseS"] + d_response
            ),
            1,
        )

        org["score"] = new_score
        org["uptime"] = new_uptime
        org["mtbf"] = new_mtbf
        org["responseS"] = new_resp

        org["trend"] = (
            "up"
            if new_score > old_score
            else "down"
            if new_score < old_score
            else org["trend"]
        )


@app.get(
    "/leaderboard",
    tags=["Leaderboard"],
)
async def get_leaderboard():
    _tick_leaderboard()

    return {
        "tick": _leaderboard_tick,
        "organisations": _leaderboard_state,
        "last_updated": time.time(),
    }
