# Design Document — AIML Predictive Maintenance

## Overview

This document defines the architecture and implementation design for upgrading IntelliWatch from a heuristic, Welford-statistics engine into a trained, continuously-learning predictive-maintenance platform. It is written against the actual current codebase:

- **Backend (Python):** `intelliwatch_brain.py` (orchestration cycle), `intelliwatch_engine.py` (Welford online mean/variance + Mahalanobis-like distance — *not* trained ML), `sensor_reader.py` (`SIMULATION_MODE = True`), `sensor_config.py`, `recommendations.py`, `database.py` (SQLite, 7 tables), `auth.py` (JWT + role guard `require_roles`), `server.py` (FastAPI stub with sensor endpoints).
- **Frontend (React):** `SensorExplorer.jsx` (3D drag-and-drop via `@react-three/fiber`, *no ML, no history*), `MLStatusPanel.jsx`, `mlEngine.js` (browser-side lightweight scorer), `sensors.js` (ISO thresholds), `Navbar.jsx` + `App.jsx` (react-router-dom, **navigation currently broken — links not visible**).
- **Data:** KAIST bearing features already extracted into CSVs under `KAIST/features/batch/{vibration,temperature_current}/`, with per-axis `rms/std/peak`, temp `mean/min/max`, current `rms/mean`, and explicit `<channel>_available` boolean columns.

The design preserves existing behavior (the Welford engine and `mlEngine.js` remain as a cold-start fallback) while adding trained models, status-aware control, an IoT integration layer, explorer ML/history, adaptive learning, ISO alignment, scalability, audit, and observability.

## Glossary

See `requirements.md` for the full glossary. Key additions used in this design:

- **Cold-start fallback**: the existing Welford heuristic engine (`intelliwatch_engine.py`) and `mlEngine.js` continue to produce a status when no trained model is loaded, so the system degrades gracefully rather than failing.
- **Model registry**: an in-memory + on-disk catalog of trained artifacts keyed by family, version, and active status.
- **Control-signal bus**: the in-process dispatcher that routes `Control_Signal` intents from the `Equipment_Controller` to the IoT layer and records audit entries.

---

## Architecture

The system is organized into six logical layers. The frontend and backend communicate over the existing FastAPI server; a new WebSocket/SSE channel carries low-latency control-signal and status updates.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FRONTEND_UI (React)                            │
│  Navbar (fixed) │ Home │ Sensor pages │ 3D Explorer (+ML +History)    │
│  MLStatusPanel │ Chatbot │ AlertLog │ ControlSignalBanner             │
└───────────────▲─────────────────────────────────────────────────────┘
                │  REST (JWT)  +  WebSocket/SSE (status/control stream)
┌───────────────┴─────────────────────────────────────────────────────┐
│                    Backend_API (FastAPI, server.py)                    │
│  auth_router │ sensor endpoints │ control endpoints │ model/status    │
│  explorer endpoints │ feedback/learning endpoints │ audit endpoints     │
└───────┬───────────────┬───────────────┬───────────────┬───────────────┘
        │               │               │               │
┌───────▼──────┐ ┌──────▼───────┐ ┌─────▼──────┐ ┌───────▼────────┐
│ Training_     │ │ Inference &   │ │ Equipment_  │ │ IoT_Integration │
│ Pipeline      │ │ Feature_      │ │ Controller   │ │ Layer (MQTT/HTTP)│
│ (offline)     │ │ Extractor     │ │ (dispatch bus)│ │ + device registry │
└──────┬───────┘ └──────┬────────┘ └──────┬───────┘ └────────┬─────────┘
       │                │                 │                   │
┌──────▼────────────────▼─────────────────▼───────────────────▼────────┐
│                  Persistence Layer (SQLite + Model Artifacts)         │
│  existing 7 tables + new tables (see §3) + trained model files on disk │
└──────────────────────────────────────────────────────────────────────┘
```

**Process boundaries:**
- The `Training_Pipeline` runs **offline** (CLI/process), reading KAIST CSVs and writing model artifacts + registry rows. It does not block the live server.
- The live path (`Inference` → `Equipment_Controller` → `IoT layer`) runs **in-process** within the FastAPI server, so the ≤500 ms SHUTDOWN and ≤200 ms status budgets are achievable without IPC overhead.
- The `Learning_System` recalibration runs as a **scheduled background task** at a configurable interval.

### Layer responsibilities

| Layer | Responsibility | New/modified module |
|-------|----------------|---------------------|
| Training_Pipeline | Load KAIST data, train/validate/persist models, emit report | NEW `training_pipeline.py`, `feature_extractor.py` |
| Inference | Per-window feature extraction + model scoring + status determination | NEW `inference.py`; extends `intelliwatch_brain.py` |
| Equipment_Controller | Map status → control signal, dispatch, retry, latch, ack, audit | NEW `equipment_controller.py` |
| IoT_Integration_Layer | Device registry, handshake, heartbeat, data forwarding, command relay, queue | NEW `iot_layer.py` + protocol adapters |
| Persistence | Schema, indexes, retention, model registry | MODIFIED `database.py`; NEW `model_registry.py` |
| Learning_System | Ingest labels, recalibrate, promote, trend | NEW `learning_system.py` |
| Observability | Endpoints + degradation alerts | MODIFIED `server.py`; NEW `obs_service.py` |

---

## Components and Interfaces

### New and Modified Backend Modules

#### 2.1 New modules

**`feature_extractor.py`** — pure functions over sensor windows (Requirement 2). Each function takes a numeric window (list/array) plus a channel id and returns a `MonitoringParameter`-shaped record. This is the unit most amenable to property-based testing (pure, input varies).

```python
# feature_extractor.py (sketch)
from dataclasses import dataclass, asdict
import math, statistics
from typing import Optional

@dataclass
class MonitoringParameter:
    name: str
    unit: str
    sensor_source: str
    timestamp: str          # ISO-8601
    value: float
    schema_version: str = "1.0"
    available: bool = True

def _safe(values):
    return [v for v in values if v is not None and math.isfinite(v)]

def vibration_features(window_x, window_y, window_z, ts, source):
    out = {}
    for axis, w in (("x", window_x), ("y", window_y), ("z", window_z)):
        wv = _safe(w)
        if not wv:
            out[f"rms_{axis}"] = MonitoringParameter(f"rms_{axis}", "g", source, ts, float("nan"), available=False)
            continue
        rms = math.sqrt(sum(v*v for v in wv) / len(wv))
        peak = max(abs(v) for v in wv)
        var = statistics.pvariance(wv)
        kurt = _kurtosis(wv, var)
        crest = peak / rms if rms else float("nan")
        for nm, val in (("rms",rms),("peak",peak),("variance",var),("kurtosis",kurt),("crest_factor",crest)):
            out[f"{nm}_{axis}"] = MonitoringParameter(f"{nm}_{axis}", "g", source, ts, val)
    return out
```

- `_kurtosis` uses the standard excess-kurtosis formula; `crest_factor = peak / rms`. These identities become correctness properties.
- Missing values (NaN/None) mark the derived parameter `available=False` (Requirement 2.7) and are excluded from model input vectors.

**`training_pipeline.py`** — orchestrates load → train → validate → persist → report (Requirements 1, 9, 10).

```python
# training_pipeline.py (sketch)
def run_training(dataset_root="KAIST/features/batch", out_dir="Backend/models"):
    unified = load_unified_training_set(dataset_root)      # Req 1.1
    X, y, meta = unified["X"], unified["y"], unified["meta"]
    models = {}
    models["tabular"] = train_tabular(X, y)                # XGBoost/LightGBM, Req 1.2
    models["unsupervised"] = train_unsupervised(X)          # IsolationForest/Autoencoder, Req 1.3
    models["sequence"] = train_sequence(make_windows(X, meta)) # LSTM/GRU, Req 1.4
    ensemble = EnsembleModel(models)                        # Req 1.5
    report = validate_and_report({**models, "ensemble": ensemble}, X, y)  # Req 1.7
    for name, m in {**models, "ensemble": ensemble}.items():
        persist_model(m, name, out_dir, dataset_hash=meta["hash"])  # Req 1.6
    registry.register_many(...)
    return report
```

- `load_unified_training_set` walks `dataset_root/vibration` and `dataset_root/temperature_current`, parses the `{Load}_{Condition}_{Severity}_*.csv` filenames into `(fault, load, severity)` labels, and concatenates all windows into one frame. The `{channel}_available` columns drive per-feature availability.
- Mini-batching (Requirement 9.2): when the frame exceeds `BATCH_SIZE`, `train_*` iterates chunks of size `<= BATCH_SIZE`. Each chunk's size is asserted bounded (a property).
- Memory-fallback (Requirement 1.8): a `try/except MemoryError`/resource-probe around model construction reduces capacity (fewer estimators / smaller hidden size) and logs a `RESOURCE_ERROR`.

**`inference.py`** — live per-window inference (Requirements 9.3, 11.1).

```python
def determine_status(feature_vector, ts):
    model = registry.active_model() or cold_start_engine   # graceful fallback
    result = model.predict_proba(feature_vector)
    status = status_from_probs(result)                     # NORMAL/WARNING/CRITICAL
    trace = DetectionTrace(inputs=feature_vector, status=status,
                            model_version=model.version, ts=ts)
    return status, trace
```

- `status_from_probs` consults the ensemble plus ISO band rules (Requirement 7.1) and takes the **most severe** of model + threshold outputs (matches existing `calculate_overall_status` semantics).
- Cold-start fallback: if no trained model is active, delegate to `intelliwatch_engine.py` so the system still produces a status.

**`equipment_controller.py`** — the control-signal dispatch bus (Requirements 3, 11, 13).

```python
class EquipmentController:
    def __init__(self, iot_layer, audit, db): ...
    def on_status(self, status, trace):
        intent = STATUS_TO_INTENT[status]            # Req 3.1/3.3/3.4
        if status == "CRITICAL":
            self.dispatch(SHUTDOWN, priority=PRIORITY_SHUTDOWN, trace=trace, deadline_ms=500)  # Req 3.5
        elif status == "WARNING":
            self.dispatch(DE_RATE, priority=PRIORITY_DE_RATE, trace=trace)
        else:
            self.dispatch(RUN, priority=PRIORITY_RUN, trace=trace)   # "no intervention" RUN
    def dispatch(self, intent, priority, trace, deadline_ms=None):
        if not authorize(self.session):                     # Req 13.3
            audit.record_rejected(intent, self.session); raise PermissionDenied
        audit.record_dispatch(intent, trace)                 # Req 13.1 (immutable)
        self._send_with_retry(intent, priority, deadline_ms) # Req 11.2
    def _latch_critical(self): ...   # while CRITICAL persists, never downgrade (Req 11.3)
    def on_ack(self, intent, ts, equip_state):
        db.save_control_ack(intent, ts, equip_state)         # Req 3.8
```

- `STATUS_TO_INTENT = {"CRITICAL":"SHUTDOWN","WARNING":"DE_RATE","NORMAL":"RUN"}`. SHUTDOWN carries the highest priority and is dispatched within 500 ms (Requirement 3.5) because the controller is in-process.
- Latching: a CRITICAL state holds SHUTDOWN until status returns to NORMAL (Requirement 11.3).
- Retry: `_send_with_retry` reattempts on transient transport failure (Requirement 11.2); if the channel is unavailable, a fail-safe alert fires within 1 s and retries continue (Requirement 11.4).

**`iot_layer.py`** — device abstraction, registry, handshake, heartbeat, queue (Requirements 4, 12).

```python
class EdgeDevice(Protocol):        # Req 4.1 abstraction
    device_id: str; capabilities: set; protocol: str
    def connect(self) -> HandshakeResult: ...
    def recv_data(self) -> bytes: ...
    def send_command(self, intent) -> Ack: ...

class IoTIntegrationLayer:
    def register_device(self, device): ...                 # Req 4.2 handshake
    def on_data(self, device_id, payload):                  # Req 4.4 forward verbatim
        forward_to_inference(payload)   # no recomputation here
    def relay(self, intent): self._send_over_active_protocol(intent)  # Req 4.5
    def on_disconnect(self, device_id): mark_offline_keep_state      # Req 4.6
    def on_reconnect(self, device_id): resume + flush_queue           # Req 4.7, 12.3
    def heartbeat_loop(self): ...                                     # Req 12.1/12.2
    def authenticate(self, device_id, credential) -> bool            # Req 12.4
    def on_malformed(self, raw): reject_log_keep_connection           # Req 12.5
```

- Protocol adapters: `MQTTAdapter` and `HTTPAdapter` (Requirement 4.3). Each implements the `EdgeDevice` protocol's transport.
- Heartbeat: a periodic ping at configurable `HEARTBEAT_INTERVAL`; if no heartbeat within `2 * INTERVAL`, the device is marked unresponsive and the UI is notified (Requirement 12.2).
- Outbound queue: while a device is disconnected, control signals are queued with timestamps; on reconnect they are flushed in priority order within a retention window (Requirement 12.3).

**`learning_system.py`** — adaptive learning loop (Requirement 8).

```python
class LearningSystem:
    def submit_label(self, event_id, label, feature_vector, model_version, user):
        db.save_verified_label(event_id, label, feature_vector, model_version, ts)  # Req 8.1/8.2
    def recalibrate(self):
        labels = db.load_verified_labels_since(...)
        candidate = train_candidate(active_model, labels)     # Req 8.3
        f1_candidate = validate(candidate); f1_active = active.f1
        if f1_candidate > f1_active:                            # Req 8.4
            registry.promote(candidate); audit.record_promotion(...)
        db.append_accuracy_trend(model_id, f1_candidate)       # Req 8.5
```

**`obs_service.py`** — observability (Requirement 14): builds the model-status and system-status responses and raises the degradation alert when a deployed metric falls >0.05 below its promotion threshold (Requirement 14.4).

#### 2.2 Modified modules

- **`intelliwatch_brain.py`** — `run_cycle` now calls `inference.determine_status` first; the Welford engine is used only as the cold-start fallback. `create_recommendations` consumes `DetectionTrace` so recommendations stay traceable to inputs (Requirement 2.6).
- **`database.py`** — `initialize_database` extended to create the new tables (§3) and the `(sensor_name, timestamp)` index (Requirement 9.4). Add helper functions for the new tables.
- **`server.py`** — add routers for control, model/status, explorer, feedback, audit, IoT (§9). Add a WebSocket/SSE endpoint for the status+control stream. Reuse `require_roles` from `auth.py` for actuation authorization (Requirement 13.3).
- **`sensor_config.py` / `sensors.js`** — thresholds gain a `source` field and an `equipment_specific` flag (Requirements 7.3/7.4). The frontend `sensors.js` already documents ISO sources; we formalize them as data.

---

## Data Models

All new tables are created idempotently by `database.initialize_database()` alongside the existing 7 tables. Existing tables are unchanged (additive migration only).

```sql
-- 8. Trained model registry
CREATE TABLE IF NOT EXISTS ml_models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family TEXT NOT NULL,                 -- tabular|unsupervised|sequence|ensemble|explorer
    model_name TEXT NOT NULL,
    version TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 0 CHECK (is_active IN (0,1)),
    training_timestamp TEXT NOT NULL,
    dataset_hash TEXT NOT NULL,
    artifact_path TEXT NOT NULL,
    metrics_json TEXT,                    -- {accuracy,precision,recall,f1,false_alarm_rate}
    schema_version TEXT DEFAULT '1.0',
    UNIQUE(family, version)
);
CREATE INDEX IF NOT EXISTS idx_ml_models_active ON ml_models(family, is_active);

-- 9. Verified labels for adaptive learning (Req 8.1/8.2)
CREATE TABLE IF NOT EXISTS verified_labels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER,
    label TEXT NOT NULL,                  -- confirm|dismiss
    feature_vector_json TEXT NOT NULL,
    model_version TEXT NOT NULL,
    verified_by TEXT NOT NULL,
    verified_at TEXT NOT NULL,
    FOREIGN KEY (event_id) REFERENCES anomaly_events(id)
);
CREATE INDEX IF NOT EXISTS idx_verified_model_ts ON verified_labels(model_version, verified_at);

-- 10. Accuracy trend per model (Req 8.5)
CREATE TABLE IF NOT EXISTS accuracy_trend (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id INTEGER NOT NULL,
    f1_score REAL NOT NULL,
    measured_at TEXT NOT NULL,
    FOREIGN KEY (model_id) REFERENCES ml_models(id)
);
CREATE INDEX IF NOT EXISTS idx_trend_model_time ON accuracy_trend(model_id, measured_at);

-- 11. Control signals + acknowledgement (Req 3.1-3.8)
CREATE TABLE IF NOT EXISTS control_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    intent TEXT NOT NULL,                 -- SHUTDOWN|DE_RATE|RUN
    system_status TEXT NOT NULL,          -- CRITICAL|WARNING|NORMAL
    target_equipment TEXT,
    priority INTEGER NOT NULL,
    triggering_params_json TEXT,
    model_version TEXT,
    ack_timestamp TEXT,
    resulting_equipment_state TEXT,
    FOREIGN KEY (model_version) REFERENCES ml_models(version)
);
CREATE INDEX IF NOT EXISTS idx_control_intent_ts ON control_signals(intent, timestamp);

-- 12. Immutable audit log (Req 13.1/13.2/13.5)
CREATE TABLE IF NOT EXISTS audit_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    category TEXT NOT NULL,                -- control_dispatch|model_promotion|recalibration|rejected_attempt
    actor TEXT,                            -- session/user
    target TEXT,
    detail_json TEXT NOT NULL,
    hash TEXT NOT NULL                     -- chain hash for tamper-evidence
);
CREATE INDEX IF NOT EXISTS idx_audit_category_ts ON audit_entries(category, timestamp);

-- 13. IoT edge devices + state (Req 4, 12)
CREATE TABLE IF NOT EXISTS edge_devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL UNIQUE,
    protocol TEXT NOT NULL,                -- MQTT|HTTP
    capabilities_json TEXT,
    status TEXT NOT NULL DEFAULT 'offline', -- online|offline|unresponsive
    last_known_state_json TEXT,
    last_heartbeat TEXT,
    registered_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_edge_status ON edge_devices(status);

-- 14. Outbound control-signal queue (Req 12.3)
CREATE TABLE IF NOT EXISTS control_signal_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    intent TEXT NOT NULL,
    priority INTEGER NOT NULL,
    queued_at TEXT NOT NULL,
    delivered_at TEXT,
    FOREIGN KEY (device_id) REFERENCES edge_devices(device_id)
);
CREATE INDEX IF NOT EXISTS idx_queue_device_delivered ON control_signal_queue(device_id, delivered_at);

-- 15. 3D Explorer history log (Req 6.1/6.2)
CREATE TABLE IF NOT EXISTS explorer_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    entry_type TEXT NOT NULL,               -- workspace_state|classification
    active_user TEXT,
    arrangement_json TEXT,                 -- component arrangement (workspace_state)
    classification_label TEXT,              -- classification
    confidence REAL,
    model_version TEXT,
    UNIQUE(timestamp, entry_type)           -- dedupe within a tick
);
CREATE INDEX IF NOT EXISTS idx_explorer_ts ON explorer_history(timestamp);

-- 16. ISO threshold definitions (Req 7.1/7.3/7.4)
CREATE TABLE IF NOT EXISTS threshold_definitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parameter_name TEXT NOT NULL,
    normal_max REAL NOT NULL,
    warning_max REAL NOT NULL,
    source_standard TEXT,                  -- e.g. 'ISO 10816-3:2009'
    equipment_specific INTEGER NOT NULL DEFAULT 0 CHECK (equipment_specific IN (0,1)),
    confirmed_by TEXT,
    confirmed_at TEXT,
    active INTEGER NOT NULL DEFAULT 0       -- equipment-specific thresholds inactive until confirmed
);
```

**Retention:** `sensor_readings`, `anomaly_events`, and `audit_entries` are retained ≥365 days (Requirement 13.4) via a nightly cleanup that deletes rows older than the cutoff (configurable). The `explorer_history` retention caps at the 500 most recent rows (Requirement 6.5/6.6) via an eviction query that deletes the oldest beyond capacity.

**Index for scale (Requirement 9.4):** a composite index on `sensor_readings(sensor_name, timestamp)` already exists; we keep it and verify query performance against ≥1,000,000 rows in an integration test.

---

## 4. Model Training Pipeline Design

### 4.1 Data loading (Requirement 1.1)

`load_unified_training_set` walks both `vibration/` and `temperature_current/` directories. The filename grammar `{Load}_{Condition}_{Severity}_{modality}_features.csv` is parsed into a label triple:

| Filename token | Fault_Type | Load_Level | Severity |
|----------------|------------|------------|----------|
| `0Nm_BPFI_03` | BPFI | 0 Nm | 03 |
| `2Nm_Unbalance_2239mg` | Unbalance | 2 Nm | 2239mg |
| `4Nm_Normal` | Normal | 4 Nm | — |
| `0Nm_Misalign_01` | Misalignment | 0 Nm | 01 |

All five faults (Normal, BPFI, BPFO, Misalignment, Unbalance), three loads (0/2/4 Nm), and all severities are unioned into one frame with a computed `dataset_hash` (SHA-256 of sorted file list + row counts). A coverage property asserts every `(fault, load)` present on disk appears in the loaded set.

### 4.2 Model families (Requirements 1.2–1.5)

- **Tabular** (Requirement 1.2): XGBoost or LightGBM multiclass classifier over the KAIST features. Default LightGBM for speed/memory; XGBoost as an alternative selectable by config.
- **Unsupervised** (Requirement 1.3): Isolation Forest (default) for label-free anomaly scoring; an autoencoder variant selectable when reconstruction-loss scoring is preferred.
- **Sequence** (Requirement 1.4): a small LSTM or GRU over consecutive `window_index` windows to capture temporal evolution. Sliding-window construction preserves order.
- **Ensemble** (Requirement 1.5): soft-voting/stacking over the three families; its combined decision is the primary classifier. The ensemble stores member references so its output is a deterministic function of member outputs (a correctness property).

### 4.3 Validation & report (Requirements 1.7, 10)

A stratified held-out split (per fault/load) computes accuracy, precision, recall, F1, and false-alarm rate. The training report emits one entry per model with these metrics in `[0,1]`. Accuracy targets gate promotion (Requirement 10): tabular ≥0.92 accuracy, unsupervised ≥0.90 F1, false-alarm rate ≤0.05. A candidate failing its target is **not** activated and the shortfall is recorded (Requirement 10.4).

### 4.4 Persistence (Requirement 1.6)

Each artifact is written under `Backend/models/{family}/{version}/` with a `manifest.json` carrying `version`, `training_timestamp`, `dataset_hash`, and metrics. Reload round-trips these fields (a property). The registry keeps one `is_active` row per family.

### 4.5 Scalability (Requirements 9.1, 9.2)

`BATCH_SIZE` config drives mini-batch iteration; each chunk is bounded by `BATCH_SIZE` (a property). The pipeline is designed to handle ≥100,000 windows; memory stays bounded because only one chunk is materialized at a time. Dask/pandas chunked reads avoid loading the entire frame.

---

## 5. Control Signal Dispatch Architecture

```
 sensor window
      │
      ▼
 inference.determine_status ──► DetectionTrace (inputs, status, model_version)
      │
      ▼
 EquipmentController.on_status
      │
      ├─ status==CRITICAL ─► dispatch(SHUTDOWN, prio=HIGH, deadline=500ms) ──┐
      ├─ status==WARNING  ─► dispatch(DE_RATE, prio=MED)                      │
      └─ status==NORMAL   ─► dispatch(RUN,     prio=LOW)                      │
                                                                              │
   authorize(session)? ──no─► audit.record_rejected; raise PermissionDenied │
        │yes                                                                  │
        ▼                                                                      │
   audit.record_dispatch(intent, trace)   [immutable, Req 13.1]              │
        │                                                                      │
        ▼                                                                      │
   _send_with_retry ──► iot_layer.relay ──► device (MQTT/HTTP)                 │
        │                                                                      │
        ▼                                                                      │
   latch: while CRITICAL, keep SHUTDOWN (no downgrade) ◄─────────────────────┘
        │
        ▼
   device.ack ──► db.save_control_ack(intent, ts, equip_state)   [Req 3.8]
        │
        └─ no ack within timeout ─► raise actuation-failure alert  [Req 3.9]
```

**Latency budget (Requirement 11.1):** status determination must complete within 200 ms of window close. Because inference runs in-process and the active model is preloaded in the registry, this is achievable; it is validated by an integration timing test.

**Priority & latching (Requirements 3.6, 11.3):** SHUTDOWN has the highest numeric priority; if a SHUTDOWN and a DE_RATE/RUN are pending simultaneously, SHUTDOWN wins. While a CRITICAL status persists, the controller holds SHUTDOWN and refuses to downgrade until status returns to NORMAL.

**Authorization (Requirement 13.3):** `dispatch` calls `authorize(session)` reusing `auth.require_roles`. Only `ADMIN`/`MAINTENANCE_ENGINEER` may issue SHUTDOWN/DE_RATE; an unauthenticated or unauthorized attempt is rejected and recorded (Requirement 13.5).

---

## 6. IoT Integration Layer Design

### 6.1 Device abstraction (Requirement 4.1)

`EdgeDevice` is a Python `Protocol` (structural interface) any adapter implements: `connect`, `recv_data`, `send_command`, plus metadata `device_id`, `capabilities`, `protocol`. Adapters: `MQTTAdapter` (paho-mqtt), `HTTPAdapter` (requests/httpx).

### 6.2 Graceful handshake (Requirements 4.2, 4.8)

On `register_device`, the layer performs a handshake exchanging identity, capability set, and protocol version. A device is accepted only if identity verifies, the capability set intersects the required capabilities, and the protocol matches. Incompatible capability → reject and log the reason. Compatible → accept. This accept/reject behavior is a property.

### 6.3 Data forwarding (Requirement 4.4)

`on_data` forwards the device's already-computed payload to inference **without recomputing** on the server. The forwarded payload equals the received payload (a fidelity property). The layer is a pass-through; the edge does its own computation.

### 6.4 Reliability (Requirements 12.1–12.5)

- **Heartbeat:** `heartbeat_loop` pings each online device at `HEARTBEAT_INTERVAL`. Missing beyond `2 * INTERVAL` → mark `unresponsive` and notify UI.
- **Queue on disconnect:** outbound control signals are appended to `control_signal_queue` while a device is disconnected; on reconnect they are flushed in priority order within `QUEUE_RETENTION_WINDOW`.
- **Authentication:** `authenticate(device_id, credential)` must succeed before any data is accepted or command relayed (an auth-gate property).
- **Malformed messages:** rejected and logged; the device connection stays open (error-isolation property).

### 6.5 Reconnect (Requirement 4.7)

On reconnect, the session is re-established, last-known state is reconciled, and the queue is flushed. Data/command exchange resumes.

---

## 7. 3D Sensor Explorer ML + History Logging

### 7.1 Explorer ML model (Requirements 5.1–5.5)

A dedicated `Explorer_ML_Model` is trained by the pipeline (family `explorer`) on `Sensor_Explorer` visualization data: the **component arrangement** (placed components, positions, rotations) plus **per-component sensor readings**. The training data is synthesized from arrangement/reading combinations with known labels.

Inference (`explorer_ml.classify(arrangement, readings)`) returns a label and confidence; the result, confidence, and model version are displayed inside `SensorExplorer.jsx` (Requirement 5.4). When the label is anomalous, contributing components are highlighted on the 3D canvas (Requirement 5.5). The classify function is a pure function over workspace state, making it a property target; the highlight is UI behavior covered by example tests.

### 7.2 History log (Requirements 6.1–6.6)

Two persistence hooks in `SensorExplorer.jsx`:

- **On workspace state change** (`commitWorkspace` / undo / redo / clear): persist a `workspace_state` entry with timestamp, arrangement JSON, active user (Requirement 6.1).
- **On each classification**: persist a `classification` entry with timestamp, label, confidence, model version (Requirement 6.2).

Both write through a new `POST /explorer/history` endpoint (or directly to `explorer_history` via a frontend API client) and are deduped within a tick via the `UNIQUE(timestamp, entry_type)` constraint.

**History view (Requirement 6.3):** a new `ExplorerHistory` sub-panel lists entries in reverse-chronological order; selecting an entry renders the recorded arrangement + classification (Requirement 6.4) by restoring `placedComponents` from the stored JSON.

**Retention (Requirements 6.5, 6.6):** the backend caps `explorer_history` at the 500 most recent rows via an eviction query run after each insert: `DELETE FROM explorer_history WHERE id NOT IN (SELECT id FROM explorer_history ORDER BY timestamp DESC LIMIT 500)`. This guarantees ≥500 recent entries are retained and the oldest are evicted (a retention/eviction property).

---

## 8. Adaptive Learning Loop Design

```
 operator verifies an anomaly event (confirm/dismiss)
        │
        ▼
 LearningSystem.submit_label(event_id, label, feature_vector, model_version, user)
        │  ──► verified_labels row (Req 8.1/8.2)
        ▼
 scheduled recalibration (configurable interval)  [Req 8.3]
        │
        ▼
 candidate = train_candidate(active_model, accumulated_labels)
 f1_candidate = validate(candidate)
        │
        ├─ f1_candidate > f1_active ─► registry.promote(candidate); audit.record_promotion  [Req 8.4]
        └─ else                      ─► keep active; audit.record_recalibration
        │
        ▼
 accuracy_trend.append(model_id, f1_candidate)   [Req 8.5]
```

- **Labels** carry the originating feature vector, the model version that produced the original decision, and the verification timestamp (Requirement 8.2).
- **Promotion gate (Requirement 8.4):** a candidate is promoted only when its validation F1 exceeds the active model's. The promotion and the comparison metrics are audited (Requirement 13.2).
- **Trend (Requirement 8.5):** each recalibration appends an F1 row to `accuracy_trend`, so the per-model trend is reconstructable.
- **Display (Requirement 8.6):** `MLStatusPanel.jsx` is extended to show model version, last recalibration timestamp, and the accuracy trend (fed from the model-status endpoint).

---

## 9. API Endpoints (New and Modified)

All new endpoints are added to `server.py` as routers, reusing `auth.require_roles` for authorization. Sensor endpoints remain. Pydantic models mirror the dataclasses.

### Control & status
| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| POST | `/control/dispatch` | Dispatch a control signal (operator-triggered) | ADMIN, MAINTENANCE_ENGINEER |
| GET  | `/control/current` | Current control-signal intent + system status (Req 14.2) | any auth |
| POST | `/control/ack` | Record equipment acknowledgement (Req 3.8) | ADMIN, MAINTENANCE_ENGINEER |
| WS   | `/stream/status` | Push status + control updates to frontend | any auth |

### Model & learning (Requirements 8, 14)
| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| GET  | `/models/status` | Active model version, last training ts, validation metrics (Req 14.1) | any auth |
| GET  | `/models/trend/{family}` | Accuracy trend for a model family (Req 8.5) | any auth |
| POST | `/learning/label` | Submit operator-verified label (Req 8.1/8.2) | OPERATOR, MAINTENANCE_ENGINEER |
| POST | `/learning/recalibrate` | Trigger recalibration (or scheduled) | ADMIN |
| GET  | `/models/degradation` | Degradation alerts (Req 14.4) | any auth |

### 3D Explorer (Requirements 5, 6)
| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| POST | `/explorer/classify` | Classify current workspace state (Req 5.2) | any auth |
| POST | `/explorer/history` | Persist a history entry (Req 6.1/6.2) | any auth |
| GET  | `/explorer/history` | List history (reverse-chronological, Req 6.3) | any auth |
| GET  | `/explorer/history/{id}` | Fetch one entry for replay (Req 6.4) | any auth |

### IoT (Requirements 4, 12)
| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| POST | `/iot/devices` | Register/connect an edge device (handshake) | ADMIN |
| GET  | `/iot/devices` | List devices + status (Req 14.2) | any auth |
| POST | `/iot/data/{device_id}` | Ingest device-computed data (Req 4.4) | device auth |
| DELETE | `/iot/devices/{device_id}` | Disconnect device | ADMIN |

### Audit (Requirement 13)
| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| GET  | `/audit/control` | Control-signal audit entries (Req 13.1) | ADMIN |
| GET  | `/audit/models` | Model change audit entries (Req 13.2) | ADMIN |

### Training (Requirement 1) — offline CLI, not HTTP
`python -m training_pipeline` runs the pipeline and writes the report; `POST /models/retrain` (ADMIN) may trigger it asynchronously if desired.

---

## 10. Frontend Component Changes

### 10.1 Navbar navigation fix (user-reported issue)

**Problem:** Users cannot see the navigation options. Root cause in the current `Navbar.jsx` + `App.css`: the `.navbar` uses a fixed `height: 56px` with `overflow: hidden`, while `.nav-links` (flex:1, nowrap children) competes for horizontal space with a wide, non-shrinking `.navbar-right` (status pill + tick + language switcher + theme toggle + user block). When the right side is wide, the centered links overflow and are clipped by `.navbar { overflow: hidden }`, so links disappear.

**Fix (two parts):**

1. **CSS (`App.css`)** — stop clipping the links and let the bar grow:
   - Change `.navbar` from `height: 56px; overflow: hidden;` to `min-height: 56px; overflow: visible;` (or `overflow-x: visible`).
   - Remove `justify-content: space-between` reliance for the links; keep logo left, links centered via `.nav-links { flex: 1; min-width: 0 }`, and right controls right-aligned.
   - Add a responsive breakpoint that collapses `.nav-links` into a hamburger menu below a threshold so links are always reachable (not clipped).

2. **Component (`Navbar.jsx`)** — add a mobile-menu toggle and render links either inline (wide) or in a dropdown panel (narrow):
   ```jsx
   const [menuOpen, setMenuOpen] = useState(false)
   const navItems = (
     <>
       <NavLink to="/" end ...>🏠 {t('nav_home', lang)}</NavLink>
       <NavLink to="/vibration" ...>{SENSORS.vibration.icon} {t('nav_vibration', lang)}</NavLink>
       <NavLink to="/temperature" ...>{SENSORS.temperature.icon} {t('nav_temperature', lang)}</NavLink>
       <NavLink to="/current" ...>{SENSORS.current.icon} {t('nav_current', lang)}</NavLink>
       <NavLink to="/explorer" ...>🧩 {t('nav_explorer', lang)}</NavLink>
       <NavLink to="/about" ...>💡 {t('nav_about', lang)}</NavLink>
     </>
   )
   // wide: inline; narrow: button toggles a <nav className="nav-links-mobile">{navItems}</nav>
   ```
   - The language switcher is unchanged; it is kept on the right and remains visible. A `ResizeObserver`/CSS media query switches between inline and collapsed layouts so links are never hidden.
   - Keep the existing routes in `App.jsx` (`/`, `/vibration`, `/temperature`, `/current`, `/explorer`, `/about`) — they already match the NavLinks, so routing is correct once links are visible.

### 10.2 Control-signal banner (Requirements 3.7, 14.2)

A new `ControlSignalBanner` (or reuse the existing `action-banner` CSS) sits below the Navbar in `ProtectedLayout`. It subscribes to the `/stream/status` WebSocket and shows the current intent (SHUTDOWN/DE_RATE/RUN) alongside the system status (Requirement 3.7). On actuation-failure or fail-safe alert, it turns red and shows the alert (Requirements 3.9, 11.4).

### 10.3 3D Sensor Explorer (Requirements 5, 6)

Modify `SensorExplorer.jsx`:
- After each `commitWorkspace`, POST the arrangement to `/explorer/history` and call `/explorer/classify`; display label + confidence + model version near the header (Requirement 5.4).
- On an anomalous classification, set a `highlightedInstanceIds` state and render contributing components with an emissive material (Requirement 5.5).
- Add an `ExplorerHistory` side panel listing history entries (reverse-chronological) with a "replay" action that restores `placedComponents` from the stored arrangement (Requirements 6.3, 6.4).

### 10.4 MLStatusPanel extension (Requirements 8.6, 14.1)

Extend `MLStatusPanel.jsx` to fetch `/models/status` and `/models/trend/{family}` and render: current model version, last recalibration timestamp, and a sparkline of the accuracy trend. The existing browser-side `mlEngine.js` remains as the cold-start/local fallback; once a backend model is active, the panel shows backend metrics.

### 10.5 Sensors thresholds (Requirements 7.1, 7.3)

`sensors.js` already documents ISO sources in comments. Promote them to a `source` field on each sensor object and add an `equipmentSpecific` flag, mirroring the backend `threshold_definitions` table, so the UI can show "equipment-specific — confirm" badges (Requirement 7.4).

---

## 11. Data Flow Diagrams (text-based)

### 11.1 Live monitoring → control loop
```
[Edge device] --computed payload--> [IoT layer.forward] --verbatim--> [feature_extractor]
      --> [inference.determine_status] --> [DetectionTrace]
      --> [EquipmentController.on_status] --> [audit.record_dispatch] --> [iot_layer.relay]
      --> [device] --ack--> [db.save_control_ack]
      --> (no ack) --> actuation-failure alert -> Frontend
```

### 11.2 Offline training → registry
```
[KAIST CSVs] --> load_unified_training_set --> [tabular|unsupervised|sequence] --> ensemble
      --> validate_and_report --> persist_model (manifest.json) --> registry.set_active
      --> accuracy_trend seed
```

### 11.3 Adaptive learning loop
```
[operator] --label--> /learning/label --> [verified_labels]
      --scheduled--> [LearningSystem.recalibrate] --> candidate
      --> validate --> (f1 > active?) promote --> registry + audit --> accuracy_trend
```

### 11.4 Explorer ML + history
```
[SensorExplorer commitWorkspace] --> /explorer/history (state) + /explorer/classify
      --> display label/confidence/version + highlight
[ExplorerHistory panel] --> GET /explorer/history --> replay arrangement
backend retention --> evict oldest beyond 500
```

---

## 12. Key Technical Decisions and Tradeoffs

| Decision | Rationale | Tradeoff |
|----------|-----------|----------|
| In-process inference (no IPC) | Meets ≤200 ms status and ≤500 ms SHUTDOWN budgets (Req 11.1, 3.5) | Coupling to the server process; mitigated by model preloading and a registry lock |
| Keep Welford engine as cold-start fallback | Preserves existing behavior; graceful degradation when no trained model loaded | Slight duplication of status logic; contained by routing through one `determine_status` |
| LightGBM default for tabular | Speed + memory efficiency for ≥100k windows (Req 9.1) | XGBoost available as config alternative if accuracy edge needed |
| Isolation Forest default for unsupervised | Simple, robust label-free anomaly scoring (Req 1.3) | Autoencoder selectable for reconstruction-loss scoring at higher cost |
| SQLite + WAL retained | Existing DB; adequate for single-machine PC deployment | Not horizontally scalable; acceptable given the "budget-friendly, PC-ready" scope |
| WebSocket/SSE for status stream | Low-latency push for control banner (Req 3.7) | Adds a persistent connection; SSE simpler if no backpressure needed |
| Additive schema migration (no breaking changes) | Zero downtime; existing tables untouched | More tables to manage; mitigated by retention cleanup jobs |
| Chain-hash audit entries | Tamper-evidence for safety-critical control (Req 13.1) | Small per-insert cost; acceptable for audit volume |
| Explorer history capped at 500 server-side | Enforces Req 6.5/6.6 deterministically even if client misbehaves | Server round-trip per state change; batched to limit calls |
| Normalize status strings (NORMAL/WARNING/CRITICAL) across backend & frontend | Single source of truth; matches existing engine output | Frontend currently uses lowercase; mapping layer added in `App.jsx` status derivation |

---

## Error Handling

The design treats errors in three tiers so that safety-critical paths never fail silently.

**Training pipeline (Requirements 1.8, 10.4):**
- Resource exhaustion (`MemoryError`/allocation failure) during model construction triggers a capacity-reduction fallback (fewer estimators / smaller hidden size) and a logged `RESOURCE_ERROR`; the run continues rather than aborting (Requirement 1.8).
- A candidate model failing its accuracy target is prevented from promotion and the shortfall is recorded in the registry (Requirement 10.4). The active model is preserved, so detection quality never regresses.

**Live inference & control (Requirements 2.7, 3.9, 11.2, 11.4):**
- Missing `Monitoring_Parameter` values in a window mark the derived feature unavailable and exclude it from model input without failing the window (Requirement 2.7). The model degrades to a partial-feature decision; if too many features are missing, the cold-start Welford engine supplies the status.
- SHUTDOWN delivery uses a retry mechanism on transient transport failure (Requirement 11.2). If the control channel is unavailable at the moment a CRITICAL condition is detected, a fail-safe alert is raised within 1 second and retries continue (Requirement 11.4).
- If equipment does not acknowledge a SHUTDOWN within a configured timeout, an actuation-failure alert surfaces on the `Frontend_UI` (Requirement 3.9).
- CRITICAL SHUTDOWN latching prevents any downgrade while CRITICAL persists (Requirement 11.3), so a transient error cannot relax a safety hold.

**IoT layer (Requirements 4.6, 4.8, 12.3, 12.5):**
- Unexpected disconnect marks the device offline, surfaces the status, and retains the last known state (Requirement 4.6). Outbound control signals are queued and delivered on reconnect (Requirement 12.3).
- Incompatible handshake capability rejects the connection and logs the reason (Requirement 4.8).
- Malformed protocol messages are rejected and logged while the device connection stays open (Requirement 12.5), isolating one bad message from dropping a live device.
- Unauthenticated device data/commands are refused at the auth gate (Requirement 12.4).

**Security & audit (Requirements 13.3, 13.5):**
- Unauthorized control-signal dispatch attempts are rejected at the authorization gate and the rejected attempt is recorded in the audit log (Requirement 13.5). Authorization uses the existing `auth.require_roles` guard so SHUTDOWN/DE_RATE only issue from authorized roles.

**Observability (Requirement 14.4):**
- When a deployed model's validation metric falls more than 0.05 below its promotion threshold, a model-degradation alert is raised on the `Frontend_UI`, prompting intervention before detection quality drops.

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Unified training-set coverage

*For any* KAIST dataset directory containing feature files for all Fault_Type, Load_Level, and Severity combinations, the `Training_Pipeline` SHALL load every `(fault, load)` tuple present on disk into the unified training set with a non-zero window count.

**Validates: Requirements 1.1**

### Property 2: Model persistence round-trip

*For any* trained `Anomaly_Detection_Model`, persisting the artifact and then reloading it SHALL preserve the version identifier, the training timestamp, and the recorded dataset hash.

**Validates: Requirements 1.6**

### Property 3: Training report completeness

*For any* `Training_Pipeline` run, the emitted training report SHALL contain exactly one metrics entry per trained model family, and each entry SHALL carry accuracy, precision, recall, and F1 score all within the valid range `[0, 1]`.

**Validates: Requirements 1.7**

### Property 4: Ensemble decision consistency

*For any* feature vector, the ensemble classifier's decision SHALL be a deterministic function of its member models' outputs, and the ensemble SHALL reference every member model that produced those outputs.

**Validates: Requirements 1.5**

### Property 5: Vibration feature statistical identities

*For any* vibration window, the `Feature_Extractor` SHALL compute per-axis RMS, peak, variance, kurtosis, and crest factor such that `crest_factor == peak / rms` and `kurtosis` satisfies the excess-kurtosis definition, for every axis that has available samples.

**Validates: Requirements 2.1**

### Property 6: FFT band-energy validity

*For any* vibration window, the `Feature_Extractor` SHALL produce at least four non-negative FFT frequency-band energy values.

**Validates: Requirements 2.2**

### Property 7: Temperature feature correctness

*For any* temperature window, the `Feature_Extractor` SHALL compute `mean` equal to the arithmetic mean of the samples, `min` and `max` equal to the window extrema, and a `rise_rate` equal to the slope over the window.

**Validates: Requirements 2.3**

### Property 8: Current feature correctness

*For any* current window per phase, the `Feature_Extractor` SHALL compute `rms` and `mean` satisfying their statistical definitions, for every phase that has available samples.

**Validates: Requirements 2.4**

### Property 9: Monitoring-parameter serialization round-trip

*For any* `Monitoring_Parameter`, serializing the record to its versioned data model and deserializing it SHALL produce an equal record carrying the name, unit, sensor source, and timestamp.

**Validates: Requirements 2.5**

### Property 10: Detection traceability

*For any* `Anomaly_Detection_Model` output, the output record SHALL reference the originating `Monitoring_Parameter` values and the resulting `System_Status` that produced it, so every detection decision is traceable to its inputs and its `Control_Signal`.

**Validates: Requirements 2.6**

### Property 11: Status-to-control-signal mapping

*For any* `System_Status`, the `Equipment_Controller` SHALL dispatch the corresponding `Control_Signal` intent: `CRITICAL → SHUTDOWN`, `WARNING → DE_RATE`, and `NORMAL → RUN` (no intervention).

**Validates: Requirements 3.1, 3.3, 3.4**

### Property 12: Critical-to-normal restoration round-trip

*For any* equipment whose status transitions from `CRITICAL` to `NORMAL`, the `Equipment_Controller` SHALL dispatch a `RUN` `Control_Signal` that restores equipment operation.

**Validates: Requirements 3.2**

### Property 13: SHUTDOWN priority dominance

*For any* simultaneous `SHUTDOWN` and `DE_RATE`/`RUN` `Control_Signal` requests, the `Equipment_Controller` SHALL select `SHUTDOWN` as the dispatched intent.

**Validates: Requirements 3.6**

### Property 14: Control-signal acknowledgement persistence

*For any* equipment acknowledgement of a `Control_Signal`, the `Equipment_Controller` SHALL record the acknowledgement timestamp and the resulting equipment state in the persistence layer.

**Validates: Requirements 3.8**

### Property 15: Handshake accept/reject correctness

*For any* edge device, the `IoT_Integration_Layer` SHALL accept the connection when identity, capability, and protocol are all compatible, and SHALL reject the connection (logging the incompatibility reason) when any are incompatible.

**Validates: Requirements 4.2, 4.8**

### Property 16: Device data forwarding fidelity

*For any* device-computed data payload, the `IoT_Integration_Layer` SHALL forward the payload to the `IntelliWatch_System` unchanged (byte-for-byte), without performing the device's on-device computation.

**Validates: Requirements 4.4**

### Property 17: Disconnect marking and last-known-state retention

*For any* connected edge device that disconnects unexpectedly, the `IoT_Integration_Layer` SHALL mark the device offline and retain its last known device state.

**Validates: Requirements 4.6**

### Property 18: Reconnect session resumption

*For any* disconnected edge device that reconnects, the `IoT_Integration_Layer` SHALL re-establish the session and resume data and command exchange.

**Validates: Requirements 4.7**

### Property 19: Explorer model classification validity

*For any* `Sensor_Explorer` workspace state, the `Explorer_ML_Model` classification SHALL return a valid classification label and a confidence value within `[0, 1]`.

**Validates: Requirements 5.2**

### Property 20: Explorer feature-vector acceptance

*For any* `Sensor_Explorer` component arrangement and per-component sensor readings, the `Explorer_ML_Model` SHALL accept them as input features and produce a non-empty, typed feature vector.

**Validates: Requirements 5.3**

### Property 21: Explorer history persistence round-trip

*For any* `Sensor_Explorer` workspace state change or `Explorer_ML_Model` classification, the persisted `Explorer_History_Log` entry SHALL round-trip equal with its timestamp, arrangement/label, confidence, model version, and active user.

**Validates: Requirements 6.1, 6.2**

### Property 22: Explorer history retention and eviction

*For any* `Explorer_History_Log` that exceeds its retention limit, the `IntelliWatch_System` SHALL retain the most recent entries (at least 500) and evict the oldest entries without manual intervention, preserving recency order.

**Validates: Requirements 6.5, 6.6**

### Property 23: ISO vibration severity classification

*For any* vibration `Monitoring_Parameter` value, the `IntelliWatch_System` SHALL classify it into Normal, Warning, or Critical consistent with the ISO 10816/20816 severity-zone band boundaries, where Normal ends at the warning threshold and Critical begins above the warning upper bound.

**Validates: Requirements 7.1**

### Property 24: Threshold source documentation

*For any* `Monitoring_Parameter` threshold, the threshold definition SHALL carry a non-empty documented source standard, or SHALL be flagged equipment-specific (and inactive until operator confirmation).

**Validates: Requirements 7.3**

### Property 25: Operator label ingestion and storage

*For any* recorded anomaly event, an operator-verified label SHALL be accepted and stored together with the originating feature vector, the model version that produced the original decision, and the verification timestamp.

**Validates: Requirements 8.1, 8.2**

### Property 26: Model promotion gate

*For any* candidate `Anomaly_Detection_Model`, the `Learning_System` SHALL promote it to active status only when it meets its accuracy target (tabular accuracy ≥0.92, unsupervised F1 ≥0.90, false-alarm rate ≤0.05) and, for recalibrated models, its validation F1 exceeds the active model's; a candidate failing its target SHALL not be promoted and the shortfall SHALL be recorded.

**Validates: Requirements 8.4, 10.1, 10.2, 10.3, 10.4**

### Property 27: Accuracy trend recording

*For any* `Anomaly_Detection_Model` recalibration event, an F1 score entry SHALL be appended to that model's accuracy trend.

**Validates: Requirements 8.5**

### Property 28: Mini-batch bounded size

*For any* training set exceeding the configured batch size, the `Training_Pipeline` SHALL process the data in mini-batches each of size no greater than the configured batch size, so memory usage stays bounded.

**Validates: Requirements 9.2**

### Property 29: SHUTDOWN delivery retry

*For any* transient delivery failure of a `CRITICAL SHUTDOWN` `Control_Signal`, the `Equipment_Controller` SHALL reattempt transmission.

**Validates: Requirements 11.2**

### Property 30: Critical SHUTDOWN latching

*For any* sustained `CRITICAL` `System_Status`, the `Equipment_Controller` SHALL maintain the `SHUTDOWN` `Control_Signal` and SHALL NOT downgrade to `DE_RATE` or `RUN` until the `System_Status` returns to `NORMAL`.

**Validates: Requirements 11.3**

### Property 31: Heartbeat timeout detection

*For any* connected edge device whose heartbeat is not received within twice the configured heartbeat interval, the `IoT_Integration_Layer` SHALL mark the device unresponsive and notify the `Frontend_UI`.

**Validates: Requirements 12.2**

### Property 32: Disconnected control-signal queueing

*For any* `Control_Signal` queued while an edge device is disconnected, the `IoT_Integration_Layer` SHALL deliver it upon reconnection within the configured queue-retention window.

**Validates: Requirements 12.3**

### Property 33: Device authentication gate

*For any* edge device, the `IoT_Integration_Layer` SHALL authenticate the device credential before accepting device data or relaying commands; an unauthenticated device SHALL have no data accepted and no commands relayed.

**Validates: Requirements 12.4**

### Property 34: Malformed-message isolation

*For any* malformed IoT protocol message, the `IoT_Integration_Layer` SHALL reject and log the message while keeping the originating device connection open.

**Validates: Requirements 12.5**

### Property 35: Control-signal audit completeness

*For any* dispatched `Control_Signal`, an immutable audit entry SHALL exist containing the timestamp, the `System_Status`, the `Control_Signal` intent, the target equipment, and the triggering `Monitoring_Parameters`.

**Validates: Requirements 13.1**

### Property 36: Model-change audit completeness

*For any* `Anomaly_Detection_Model` promotion or recalibration, an audit entry SHALL exist containing the model version, the trigger, and the resulting accuracy metrics.

**Validates: Requirements 13.2**

### Property 37: Control-signal authorization gate

*For any* `SHUTDOWN` or `DE_RATE` `Control_Signal` dispatch, the requesting session SHALL be authenticated and hold an authorized role; an unauthenticated or unauthorized attempt SHALL be rejected and the rejected attempt SHALL be recorded.

**Validates: Requirements 13.3, 13.5**

### Property 38: Event-log completeness

*For any* `Training_Pipeline` run, `Anomaly_Detection_Model` recalibration, or `Learning_System` feedback ingestion, an event-log entry SHALL exist with a timestamp and an outcome.

**Validates: Requirements 14.3**

### Property 39: Model-degradation alerting (edge case)

*For any* deployed `Anomaly_Detection_Model` whose latest validation metric falls more than `0.05` below its promotion threshold, the `IntelliWatch_System` SHALL raise a model-degradation alert on the `Frontend_UI`.

**Validates: Requirements 14.4**

### Property 40: Missing-value window resilience (edge case)

*For any* window in which one or more `Monitoring_Parameter` values are missing, the `Feature_Extractor` SHALL mark the corresponding derived features as unavailable and exclude them from the model input without failing the whole window.

**Validates: Requirements 2.7**

---

## Testing Strategy

**Dual approach — unit tests + property tests, complemented by integration/smoke tests for infrastructure.**

- **Property tests (Properties 1–40)** run with a minimum of 100 iterations each due to randomization. Pure-function targets (`feature_extractor`, `explorer_ml.classify`, status mapping, serialization round-trips, retention/eviction, queue/auth/malformed logic) use Hypothesis-style generators. Each property test is tagged `Feature: aiml-predictive-maintenance, Property N: <text>`.
- **Unit tests** cover specific examples and component integration points (e.g., a known vibration window producing known RMS), matching the existing `Backend/tests/test_engine.py` style with isolated temp SQLite databases.
- **Integration tests** (1–3 examples, not PBT): ≥100k-window training memory (Req 9.1), ≤100 ms inference timing (Req 9.3), ≥1M-row indexed query (Req 9.4), ≤200 ms status determination (Req 11.1), ≤500 ms SHUTDOWN dispatch (Req 3.5), ≤1 s fail-safe alert (Req 11.4), 365-day retention (Req 13.4), MQTT+HTTP protocol wiring (Req 4.3), heartbeat interval (Req 12.1), model/system status endpoints (Req 14.1/14.2).
- **Smoke tests** (single execution): protocol availability, endpoint contracts, service startup with valid configuration.

**Frontend tests:** example-based tests for the Navbar responsive collapse (links visible at every viewport width), the control-signal banner rendering, and explorer history replay. Visual/layout aspects use snapshot tests rather than properties.
