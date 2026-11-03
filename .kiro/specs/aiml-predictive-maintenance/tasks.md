# Implementation Plan: AIML Predictive Maintenance

## Overview

This plan upgrades IntelliWatch from a heuristic Welford-statistics engine into a trained, continuously-learning predictive-maintenance platform. It is organized so that foundational layers (database schema, model registry, feature extraction) come first, followed by the offline training pipeline, then the live inference → control → IoT loop, the adaptive learning and observability services, the API surface, and finally the frontend ML/history/navigation work. Each step builds on the previous one and the plan ends by wiring everything together inside the existing `intelliwatch_brain.py` orchestration cycle and FastAPI server startup.

Implementation language is already fixed by the codebase: **Python** for the backend (FastAPI + SQLite) and **JavaScript/JSX (React)** for the frontend. The KAIST bearing features under `KAIST/features/batch/{vibration,temperature_current}/` are the training data source.

**Conventions used in this plan:**
- Sub-tasks postfixed with `*` are optional (tests). The implementer MUST implement non-`*` sub-tasks and SHOULD implement `*` sub-tasks.
- Each property-based test sub-task references its **Property N** from `design.md` §Correctness Properties and the requirement clause it validates. Property tests use Hypothesis-style generators with a minimum of 100 iterations, matching the design's testing strategy. Frontend tests are example/snapshot based.
- Affected files and requirements are listed as sub-bullets under each task.

---

## Tasks

- [x] 1. Fix frontend navigation (blocking user-reported issue)
  - [x] 1.1 Fix Navbar.jsx and App.css navigation visibility and responsive collapse
    - Change `.navbar` from `height: 56px; overflow: hidden;` to `min-height: 56px; overflow: visible;` so centered links are no longer clipped
    - Add a responsive breakpoint that collapses `.nav-links` into a hamburger/dropdown menu below a width threshold, with a `menuOpen` state toggle in `Navbar.jsx`
    - Render the existing NavLinks (`/`, `/vibration`, `/temperature`, `/current`, `/explorer`, `/about`) inline when wide and in a `nav-links-mobile` panel when narrow; keep the language switcher on the right and visible at all widths
    - Keep existing routes in `App.jsx` unchanged (they already match the NavLinks)
    - _Affected files: `frontend/src/components/Navbar.jsx`, `frontend/src/App.css`_
    - _Requirements: design §10.1 (Navbar fix)_
  - [ ]* 1.2 Write frontend tests for Navbar responsive collapse
    - Assert NavLinks are visible at every viewport width (wide inline, narrow dropdown)
    - Use snapshot/example tests for the collapse behavior
    - _Affected files: `frontend/src/components/__tests__/Navbar.test.jsx` (new)_
    - _Requirements: design §10.1_

- [ ] 2. Database schema and persistence layer
  - [x] 2.1 Add the 9 new tables and indexes to `database.initialize_database()`
    - Create idempotently (additive migration; do not alter the existing 7 tables): `ml_models`, `verified_labels`, `accuracy_trend`, `control_signals`, `audit_entries`, `edge_devices`, `control_signal_queue`, `explorer_history`, `threshold_definitions` per design §3
    - Add indexes: `idx_ml_models_active`, `idx_verified_model_ts`, `idx_trend_model_time`, `idx_control_intent_ts`, `idx_audit_category_ts`, `idx_edge_status`, `idx_queue_device_delivered`, `idx_explorer_ts`; keep the existing `idx_sensor_name_timestamp` (Req 9.4)
    - Add the `audit_entries.hash` chain-hash column for tamper-evidence (Req 13.1)
    - _Affected files: `Backend/database.py`_
    - _Requirements: 2.5, 3.8, 6.1, 6.2, 7.3, 8.1, 8.2, 8.5, 9.4, 13.1, 13.2, 13.4_
  - [x] 2.2 Add helper functions for the new tables
    - `save_control_ack`, `record_audit_entry` (with chain hash), `save_verified_label`, `append_accuracy_trend`, `save_explorer_history_entry`, `get_explorer_history(limit)`, `get_explorer_history_entry(id)`, `upsert_threshold_definition`, `get_threshold_definition`, plus edge-device and queue CRUD helpers
    - Mirror the style of existing helpers (`save_sensor_readings`, `save_anomaly_event`)
    - _Affected files: `Backend/database.py`_
    - _Requirements: 3.8, 6.1, 6.2, 8.1, 8.2, 8.5, 13.1_
  - [x] 2.3 Implement explorer history retention/eviction and 365-day retention cleanup
    - After each explorer-history insert, evict oldest beyond 500 rows (Req 6.5/6.6)
    - Add a nightly-style cleanup that deletes `sensor_readings`, `anomaly_events`, and `audit_entries` older than a configurable cutoff (≥365 days, Req 13.4)
    - _Affected files: `Backend/database.py`_
    - _Requirements: 6.5, 6.6, 13.4_
  - [x]* 2.4 Write property test for explorer history retention and eviction
    - **Property 22: Explorer history retention and eviction**
    - **Validates: Requirements 6.5, 6.6**
    - Assert that after inserting >500 entries, exactly the 500 most recent remain in recency order
    - _Affected files: `Backend/tests/properties/test_property_22.py` (new)_
  - [ ]* 2.5 Write unit tests for database schema and helpers
    - Verify all 9 new tables + indexes exist after `initialize_database()`; verify helper round-trips using an isolated temp SQLite DB (match `test_engine.py` style)
    - _Affected files: `Backend/tests/test_database_schema.py` (new)_
    - _Requirements: 2.5, 3.8, 6.1, 8.1, 13.1_

- [x] 3. Model registry
  - [x] 3.1 Implement model_registry.py (in-memory + on-disk catalog)
    - `register(model, family, version)`, `set_active(family, version)`, `active_model(family)`, `get_manifest(family, version)`, and on-disk lookup under `Backend/models/{family}/{version}/`
    - One `is_active` row per family; thread-safe access for the in-process live path
    - _Affected files: `Backend/model_registry.py` (new)_
    - _Requirements: 1.6, 8.4, 14.1_
  - [x]* 3.2 Write property test for model persistence round-trip
    - **Property 2: Model persistence round-trip**
    - **Validates: Requirements 1.6**
    - Persist a model artifact, reload it, and assert the version identifier, training timestamp, and dataset hash are preserved
    - _Affected files: `Backend/tests/properties/test_property_02.py` (new)_

- [x] 4. Feature extraction module
  - [x] 4.1 Implement MonitoringParameter dataclass and serialization round-trip
    - `@dataclass MonitoringParameter(name, unit, sensor_source, timestamp, value, schema_version, available)` with `to_dict`/`from_dict` round-trip (Req 2.5)
    - `_safe(values)` helper that filters `None`/non-finite values
    - _Affected files: `Backend/feature_extractor.py` (new)_
    - _Requirements: 2.5_
  - [x]* 4.2 Write property test for monitoring-parameter serialization round-trip
    - **Property 9: Monitoring-parameter serialization round-trip**
    - **Validates: Requirements 2.5**
    - _Affected files: `Backend/tests/properties/test_property_09.py` (new)_
  - [x] 4.3 Implement vibration feature extraction (RMS, peak, variance, kurtosis, crest factor per axis)
    - Compute per-axis `rms = sqrt(mean(x^2))`, `peak = max(|x|)`, `variance`, excess `kurtosis`, `crest_factor = peak / rms` for x/y/z (Req 2.1)
    - _Affected files: `Backend/feature_extractor.py`_
    - _Requirements: 2.1_
  - [x]* 4.4 Write property test for vibration feature statistical identities
    - **Property 5: Vibration feature statistical identities**
    - **Validates: Requirements 2.1**
    - Assert `crest_factor == peak / rms` and kurtosis satisfies the excess-kurtosis definition for every available axis
    - _Affected files: `Backend/tests/properties/test_property_05.py` (new)_
  - [x] 4.5 Implement FFT band-energy extraction (at least four defined bands)
    - Compute non-negative FFT frequency-band energy across ≥4 bands per vibration window (Req 2.2)
    - _Affected files: `Backend/feature_extractor.py`_
    - _Requirements: 2.2_
  - [ ]* 4.6 Write property test for FFT band-energy validity
    - **Property 6: FFT band-energy validity**
    - **Validates: Requirements 2.2**
    - Assert at least four non-negative band-energy values for any vibration window
    - _Affected files: `Backend/tests/properties/test_property_06.py` (new)_
  - [x] 4.7 Implement temperature feature extraction (mean, min, max, rise rate)
    - `mean` = arithmetic mean, `min`/`max` = window extrema, `rise_rate` = slope over the window (Req 2.3)
    - _Affected files: `Backend/feature_extractor.py`_
    - _Requirements: 2.3_
  - [ ]* 4.8 Write property test for temperature feature correctness
    - **Property 7: Temperature feature correctness**
    - **Validates: Requirements 2.3**
    - _Affected files: `Backend/tests/properties/test_property_07.py` (new)_
  - [x] 4.9 Implement current feature extraction (rms, mean, variation per phase)
    - Per-phase `rms` and `mean` satisfying statistical definitions (Req 2.4)
    - _Affected files: `Backend/feature_extractor.py`_
    - _Requirements: 2.4_
  - [ ]* 4.10 Write property test for current feature correctness
    - **Property 8: Current feature correctness**
    - **Validates: Requirements 2.4**
    - _Affected files: `Backend/tests/properties/test_property_08.py` (new)_
  - [x] 4.11 Implement missing-value window resilience
    - When a Monitoring_Parameter value is missing/NaN/None, mark the derived feature `available=False` and exclude it from the model input vector without failing the whole window (Req 2.7)
    - _Affected files: `Backend/feature_extractor.py`_
    - _Requirements: 2.7_
  - [ ]* 4.12 Write property test for missing-value window resilience
    - **Property 40: Missing-value window resilience (edge case)**
    - **Validates: Requirements 2.7**
    - _Affected files: `Backend/tests/properties/test_property_40.py` (new)_

- [x] 5. Training pipeline
  - [x] 5.1 Implement load_unified_training_set (KAIST loader)
    - Walk `KAIST/features/batch/{vibration,temperature_current}/`, parse `{Load}_{Condition}_{Severity}_{modality}_features.csv` into `(fault, load, severity)` labels, union all Fault_Type/Load_Level/Severity combos into one frame (Req 1.1)
    - Compute a SHA-256 `dataset_hash` over the sorted file list + row counts; honor `{channel}_available` columns for per-feature availability
    - _Affected files: `Backend/training_pipeline.py` (new)_
    - _Requirements: 1.1_
  - [ ]* 5.2 Write property test for unified training-set coverage
    - **Property 1: Unified training-set coverage**
    - **Validates: Requirements 1.1**
    - Assert every `(fault, load)` tuple present on disk appears in the loaded set with a non-zero window count
    - _Affected files: `Backend/tests/properties/test_property_01.py` (new)_
  - [x] 5.3 Implement tabular model training (LightGBM, XGBoost selectable)
    - Multiclass gradient-boosted-tree classifier over KAIST features (Req 1.2)
    - _Affected files: `Backend/training_pipeline.py`_
    - _Requirements: 1.2, 10.1_
  - [x] 5.4 Implement unsupervised model training (Isolation Forest, autoencoder selectable)
    - Label-free anomaly scorer (Req 1.3)
    - _Affected files: `Backend/training_pipeline.py`_
    - _Requirements: 1.3, 10.2_
  - [x] 5.5 Implement sequence model training (LSTM/GRU over consecutive windows)
    - Sliding-window construction preserving `window_index` order (Req 1.4)
    - _Affected files: `Backend/training_pipeline.py`_
    - _Requirements: 1.4_
  - [x] 5.6 Implement ensemble model (soft-voting/stacking)
    - Combined decision is the primary classifier; the ensemble stores member references so its output is a deterministic function of member outputs (Req 1.5)
    - _Affected files: `Backend/training_pipeline.py`_
    - _Requirements: 1.5_
  - [ ]* 5.7 Write property test for ensemble decision consistency
    - **Property 4: Ensemble decision consistency**
    - **Validates: Requirements 1.5**
    - Assert the ensemble decision is a deterministic function of member outputs and references every member
    - _Affected files: `Backend/tests/properties/test_property_04.py` (new)_
  - [x] 5.8 Implement validation and training report (accuracy/precision/recall/F1/false-alarm)
    - Stratified held-out split per fault/load; emit one metrics entry per model family with all metrics in `[0,1]` (Req 1.7)
    - Gate promotion by accuracy targets: tabular ≥0.92 accuracy, unsupervised ≥0.90 F1, false-alarm ≤0.05; a failing candidate is not activated and the shortfall is recorded (Req 10.1–10.4)
    - _Affected files: `Backend/training_pipeline.py`_
    - _Requirements: 1.7, 10.1, 10.2, 10.3, 10.4_
  - [ ]* 5.9 Write property test for training report completeness
    - **Property 3: Training report completeness**
    - **Validates: Requirements 1.7**
    - Assert exactly one metrics entry per family, each metric within `[0,1]`
    - _Affected files: `Backend/tests/properties/test_property_03.py` (new)_
  - [x] 5.10 Implement model persistence (manifest.json), mini-batching, memory fallback, and accuracy gating wiring
    - Write artifacts under `Backend/models/{family}/{version}/` with `manifest.json` (`version`, `training_timestamp`, `dataset_hash`, metrics) and register with `model_registry` (Req 1.6)
    - Mini-batch iteration when frame exceeds `BATCH_SIZE` (Req 9.2); `try/except` resource-probe reduces capacity (fewer estimators / smaller hidden) and logs `RESOURCE_ERROR` without aborting (Req 1.8)
    - _Affected files: `Backend/training_pipeline.py`_
    - _Requirements: 1.6, 1.8, 9.1, 9.2_
  - [ ]* 5.11 Write property test for mini-batch bounded size
    - **Property 28: Mini-batch bounded size**
    - **Validates: Requirements 9.2**
    - Assert each mini-batch chunk size ≤ configured `BATCH_SIZE`
    - _Affected files: `Backend/tests/properties/test_property_28.py` (new)_

- [x] 6. Inference module
  - [x] 6.1 Implement inference.py (determine_status, cold-start fallback, DetectionTrace)
    - `determine_status(feature_vector, ts)` uses `model_registry.active_model()`; if none active, fall back to the Welford `intelliwatch_engine.py` (cold-start) so the system still produces a status
    - `status_from_probs` combines ensemble output with ISO band rules and takes the most severe of model + threshold outputs (Req 7.1, matches existing `calculate_overall_status`)
    - `DetectionTrace` references the originating Monitoring_Parameter values, the model version, and the resulting System_Status so every decision is traceable (Req 2.6)
    - _Affected files: `Backend/inference.py` (new)_
    - _Requirements: 2.6, 7.1, 9.3, 11.1_
  - [x]* 6.2 Write property test for detection traceability
    - **Property 10: Detection traceability**
    - **Validates: Requirements 2.6**
    - Assert the DetectionTrace references inputs and the resulting System_Status
    - _Affected files: `Backend/tests/properties/test_property_10.py` (new)_

- [x] 7. Equipment controller
  - [x] 7.1 Implement EquipmentController (status→intent mapping, dispatch, SHUTDOWN priority, CRITICAL→NORMAL restoration)
    - `STATUS_TO_INTENT = {"CRITICAL":"SHUTDOWN","WARNING":"DE_RATE","NORMAL":"RUN"}`; SHUTDOWN carries the highest numeric priority (Req 3.1, 3.3, 3.4, 3.6)
    - On CRITICAL→NORMAL transition, dispatch RUN to restore operation (Req 3.2)
    - In-process dispatch so the SHUTDOWN ≤500 ms budget is achievable (Req 3.5)
    - _Affected files: `Backend/equipment_controller.py` (new)_
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_
  - [x]* 7.2 Write property test for status-to-control-signal mapping
    - **Property 11: Status-to-control-signal mapping**
    - **Validates: Requirements 3.1, 3.3, 3.4**
    - _Affected files: `Backend/tests/properties/test_property_11.py` (new)_
  - [ ]* 7.3 Write property test for critical-to-normal restoration round-trip
    - **Property 12: Critical-to-normal restoration round-trip**
    - **Validates: Requirements 3.2**
    - _Affected files: `Backend/tests/properties/test_property_12.py` (new)_
  - [x]* 7.4 Write property test for SHUTDOWN priority dominance
    - **Property 13: SHUTDOWN priority dominance**
    - **Validates: Requirements 3.6**
    - _Affected files: `Backend/tests/properties/test_property_13.py` (new)_
  - [x] 7.5 Implement SHUTDOWN delivery retry, CRITICAL latching, and fail-safe alert
    - `_send_with_retry` reattempts on transient transport failure (Req 11.2); while CRITICAL persists, hold SHUTDOWN and refuse to downgrade to DE_RATE/RUN until status returns to NORMAL (Req 11.3)
    - If the control channel is unavailable at CRITICAL detection, raise a fail-safe alert within 1 s and keep retrying (Req 11.4)
    - _Affected files: `Backend/equipment_controller.py`_
    - _Requirements: 11.2, 11.3, 11.4_
  - [ ]* 7.6 Write property test for SHUTDOWN delivery retry
    - **Property 29: SHUTDOWN delivery retry**
    - **Validates: Requirements 11.2**
    - _Affected files: `Backend/tests/properties/test_property_29.py` (new)_
  - [ ]* 7.7 Write property test for critical SHUTDOWN latching
    - **Property 30: Critical SHUTDOWN latching**
    - **Validates: Requirements 11.3**
    - _Affected files: `Backend/tests/properties/test_property_30.py` (new)_
  - [x] 7.8 Implement authorization gate, control-signal audit, and acknowledgement persistence
    - `dispatch` calls `authorize(session)` reusing `auth.require_roles`; only ADMIN/MAINTENANCE_ENGINEER may issue SHUTDOWN/DE_RATE; unauthorized attempts are rejected and recorded (Req 13.3, 13.5)
    - Record an immutable audit entry per dispatch via `record_audit_entry` (chain hash) containing timestamp, System_Status, intent, target equipment, triggering params (Req 13.1)
    - On equipment ack, record ack timestamp + resulting equipment state (Req 3.8); if no ack within timeout, raise an actuation-failure alert (Req 3.9)
    - _Affected files: `Backend/equipment_controller.py`_
    - _Requirements: 3.8, 3.9, 13.1, 13.3, 13.5_
  - [ ]* 7.9 Write property test for control-signal authorization gate
    - **Property 37: Control-signal authorization gate**
    - **Validates: Requirements 13.3, 13.5**
    - _Affected files: `Backend/tests/properties/test_property_37.py` (new)_
  - [ ]* 7.10 Write property test for control-signal audit completeness
    - **Property 35: Control-signal audit completeness**
    - **Validates: Requirements 13.1**
    - _Affected files: `Backend/tests/properties/test_property_35.py` (new)_
  - [ ]* 7.11 Write property test for control-signal acknowledgement persistence
    - **Property 14: Control-signal acknowledgement persistence**
    - **Validates: Requirements 3.8**
    - _Affected files: `Backend/tests/properties/test_property_14.py` (new)_

- [x] 8. IoT integration layer
  - [x] 8.1 Implement EdgeDevice protocol and MQTT/HTTP adapters
    - `EdgeDevice` Python `Protocol` (structural interface): `device_id`, `capabilities`, `protocol`, `connect`, `recv_data`, `send_command` (Req 4.1)
    - `MQTTAdapter` (paho-mqtt) and `HTTPAdapter` (httpx) implementing the transport (Req 4.3)
    - _Affected files: `Backend/iot_layer.py` (new)_
    - _Requirements: 4.1, 4.3_
  - [x] 8.2 Implement handshake (accept/reject) and data forwarding (verbatim)
    - `register_device` performs a graceful boot handshake verifying identity, capability set, and protocol compatibility; incompatible capability → reject and log the reason (Req 4.2, 4.8)
    - `on_data` forwards the device's already-computed payload to inference without recomputing on the server (Req 4.4)
    - _Affected files: `Backend/iot_layer.py`_
    - _Requirements: 4.2, 4.4, 4.8_
  - [ ]* 8.3 Write property test for handshake accept/reject correctness
    - **Property 15: Handshake accept/reject correctness**
    - **Validates: Requirements 4.2, 4.8**
    - _Affected files: `Backend/tests/properties/test_property_15.py` (new)_
  - [ ]* 8.4 Write property test for device data forwarding fidelity
    - **Property 16: Device data forwarding fidelity**
    - **Validates: Requirements 4.4**
    - Assert forwarded payload equals received payload byte-for-byte
    - _Affected files: `Backend/tests/properties/test_property_16.py` (new)_
  - [x] 8.5 Implement disconnect marking, reconnect resumption, and heartbeat/timeout
    - On unexpected disconnect: mark device offline, surface status, retain last known state (Req 4.6); on reconnect: re-establish session and resume data/command exchange (Req 4.7)
    - `heartbeat_loop` pings each online device at `HEARTBEAT_INTERVAL`; missing beyond `2 * INTERVAL` → mark `unresponsive` and notify UI (Req 12.1, 12.2)
    - _Affected files: `Backend/iot_layer.py`_
    - _Requirements: 4.6, 4.7, 12.1, 12.2_
  - [ ]* 8.6 Write property test for disconnect marking and last-known-state retention
    - **Property 17: Disconnect marking and last-known-state retention**
    - **Validates: Requirements 4.6**
    - _Affected files: `Backend/tests/properties/test_property_17.py` (new)_
  - [ ]* 8.7 Write property test for reconnect session resumption
    - **Property 18: Reconnect session resumption**
    - **Validates: Requirements 4.7**
    - _Affected files: `Backend/tests/properties/test_property_18.py` (new)_
  - [ ]* 8.8 Write property test for heartbeat timeout detection
    - **Property 31: Heartbeat timeout detection**
    - **Validates: Requirements 12.2**
    - _Affected files: `Backend/tests/properties/test_property_31.py` (new)_
  - [x] 8.9 Implement control-signal queue on disconnect, device auth gate, and malformed-message isolation
    - Queue outbound control signals while a device is disconnected; on reconnect flush in priority order within `QUEUE_RETENTION_WINDOW` (Req 12.3)
    - `authenticate(device_id, credential)` must succeed before any data is accepted or command relayed (Req 12.4)
    - Malformed protocol messages are rejected and logged while the device connection stays open (Req 12.5)
    - Relay Control_Signals from the Equipment_Controller over the device's active protocol (Req 4.5)
    - _Affected files: `Backend/iot_layer.py`_
    - _Requirements: 4.5, 12.3, 12.4, 12.5_
  - [ ]* 8.10 Write property test for disconnected control-signal queueing
    - **Property 32: Disconnected control-signal queueing**
    - **Validates: Requirements 12.3**
    - _Affected files: `Backend/tests/properties/test_property_32.py` (new)_
  - [ ]* 8.11 Write property test for device authentication gate
    - **Property 33: Device authentication gate**
    - **Validates: Requirements 12.4**
    - _Affected files: `Backend/tests/properties/test_property_33.py` (new)_
  - [ ]* 8.12 Write property test for malformed-message isolation
    - **Property 34: Malformed-message isolation**
    - **Validates: Requirements 12.5**
    - _Affected files: `Backend/tests/properties/test_property_34.py` (new)_

- [x] 9. ISO standards and thresholds
  - [x] 9.1 Implement ISO 10816/20816 vibration severity zones and ISO 17359 workflow
    - Classify a vibration Monitoring_Parameter into Normal/Warning/Critical using ISO 10816/20816 severity-zone band boundaries (Normal ends at warning threshold, Critical begins above the warning upper bound) (Req 7.1)
    - Structure Monitoring_Parameter acquisition/analysis/recommendation per ISO 17359 guidance (Req 7.2)
    - _Affected files: `Backend/iso_standards.py` (new)_
    - _Requirements: 7.1, 7.2_
  - [x]* 9.2 Write property test for ISO vibration severity classification
    - **Property 23: ISO vibration severity classification**
    - **Validates: Requirements 7.1**
    - _Affected files: `Backend/tests/properties/test_property_23.py` (new)_
  - [x] 9.3 Implement threshold source documentation and equipment-specific flag
    - Each threshold definition carries a non-empty documented source standard OR is flagged `equipment_specific` and inactive until operator confirmation (Req 7.3, 7.4)
    - Add `source` field and `equipmentSpecific` flag to `sensor_config.py` thresholds and `frontend/src/sensors.js` (formalize the existing ISO-source comments as data) so the UI can show "equipment-specific — confirm" badges
    - _Affected files: `Backend/sensor_config.py`, `frontend/src/sensors.js`_
    - _Requirements: 7.3, 7.4_
  - [x]* 9.4 Write property test for threshold source documentation
    - **Property 24: Threshold source documentation**
    - **Validates: Requirements 7.3**
    - _Affected files: `Backend/tests/properties/test_property_24.py` (new)_

- [x] 10. Adaptive learning system
  - [x] 10.1 Implement LearningSystem.submit_label
    - Accept operator-verified labels (confirm/dismiss) and store with the originating feature vector, the model version that produced the original decision, and the verification timestamp (Req 8.1, 8.2)
    - _Affected files: `Backend/learning_system.py` (new)_
    - _Requirements: 8.1, 8.2_
  - [ ]* 10.2 Write property test for operator label ingestion and storage
    - **Property 25: Operator label ingestion and storage**
    - **Validates: Requirements 8.1, 8.2**
    - _Affected files: `Backend/tests/properties/test_property_25.py` (new)_
  - [x] 10.3 Implement recalibration, promotion gate, and accuracy trend
    - At a configurable interval, train a candidate from accumulated labels and validate it (Req 8.3); promote only when its F1 exceeds the active model's and it meets accuracy targets (Req 8.4, 10.1–10.4)
    - Append an F1 entry to `accuracy_trend` per recalibration (Req 8.5); record an audit entry for every promotion/recalibration with model version, trigger, and resulting metrics (Req 13.2)
    - _Affected files: `Backend/learning_system.py`_
    - _Requirements: 8.3, 8.4, 8.5, 10.1, 10.2, 10.3, 10.4, 13.2_
  - [ ]* 10.4 Write property test for model promotion gate
    - **Property 26: Model promotion gate**
    - **Validates: Requirements 8.4, 10.1, 10.2, 10.3, 10.4**
    - _Affected files: `Backend/tests/properties/test_property_26.py` (new)_
  - [ ]* 10.5 Write property test for accuracy trend recording
    - **Property 27: Accuracy trend recording**
    - **Validates: Requirements 8.5**
    - _Affected files: `Backend/tests/properties/test_property_27.py` (new)_
  - [ ]* 10.6 Write property test for model-change audit completeness
    - **Property 36: Model-change audit completeness**
    - **Validates: Requirements 13.2**
    - _Affected files: `Backend/tests/properties/test_property_36.py` (new)_

- [x] 11. Observability service
  - [x] 11.1 Implement obs_service.py (model/system status responses)
    - Build the model-status response (active version, last training timestamp, validation metrics — Req 14.1) and the system-status response (current System_Status, current Control_Signal intent, connected Edge_Device status — Req 14.2)
    - _Affected files: `Backend/obs_service.py` (new)_
    - _Requirements: 14.1, 14.2_
  - [x] 11.2 Implement model-degradation alerting and event-log completeness
    - Raise a model-degradation alert when a deployed metric falls >0.05 below its promotion threshold (Req 14.4)
    - Log every Training_Pipeline run, recalibration, and feedback ingestion with a timestamp and outcome (Req 14.3)
    - _Affected files: `Backend/obs_service.py`_
    - _Requirements: 14.3, 14.4_
  - [ ]* 11.3 Write property test for model-degradation alerting
    - **Property 39: Model-degradation alerting (edge case)**
    - **Validates: Requirements 14.4**
    - _Affected files: `Backend/tests/properties/test_property_39.py` (new)_
  - [ ]* 11.4 Write property test for event-log completeness
    - **Property 38: Event-log completeness**
    - **Validates: Requirements 14.3**
    - _Affected files: `Backend/tests/properties/test_property_38.py` (new)_

- [x] 12. API endpoints (server.py)
  - [x] 12.1 Add control/status endpoints and WebSocket/SSE status stream
    - `POST /control/dispatch` (ADMIN, MAINTENANCE_ENGINEER), `GET /control/current` (any auth), `POST /control/ack` (ADMIN, MAINTENANCE_ENGINEER), `WS /stream/status` (any auth) (Req 3.7, 14.2)
    - Reuse `auth.require_roles` for authorization
    - _Affected files: `Backend/server.py`_
    - _Requirements: 3.7, 3.9, 11.4, 13.3, 14.2_
  - [x] 12.2 Add model/learning endpoints
    - `GET /models/status` (any auth, Req 14.1), `GET /models/trend/{family}` (any auth, Req 8.5), `POST /learning/label` (OPERATOR, MAINTENANCE_ENGINEER), `POST /learning/recalibrate` (ADMIN), `GET /models/degradation` (any auth, Req 14.4)
    - _Affected files: `Backend/server.py`_
    - _Requirements: 8.1, 8.5, 14.1, 14.4_
  - [x] 12.3 Add 3D Explorer endpoints
    - `POST /explorer/classify` (any auth, Req 5.2), `POST /explorer/history` (any auth, Req 6.1/6.2), `GET /explorer/history` (reverse-chronological, Req 6.3), `GET /explorer/history/{id}` (Req 6.4)
    - _Affected files: `Backend/server.py`_
    - _Requirements: 5.2, 6.1, 6.2, 6.3, 6.4_
  - [x] 12.4 Add IoT endpoints
    - `POST /iot/devices` (ADMIN, handshake), `GET /iot/devices` (any auth, Req 14.2), `POST /iot/data/{device_id}` (device auth, Req 4.4), `DELETE /iot/devices/{device_id}` (ADMIN)
    - _Affected files: `Backend/server.py`_
    - _Requirements: 4.2, 4.4, 14.2_
  - [x] 12.5 Add audit endpoints
    - `GET /audit/control` (ADMIN, Req 13.1), `GET /audit/models` (ADMIN, Req 13.2)
    - _Affected files: `Backend/server.py`_
    - _Requirements: 13.1, 13.2_
  - [ ]* 12.6 Write endpoint contract/integration tests
    - Smoke tests for endpoint contracts, role enforcement, and service startup with valid config (design §Testing Strategy)
    - _Affected files: `Backend/tests/test_server_endpoints.py` (new)_
    - _Requirements: 3.7, 5.2, 6.3, 13.3, 14.1, 14.2_

- [x] 13. Frontend: 3D Sensor Explorer ML and history
  - [x] 13.1 Implement explorer ML model training and classify (backend)
    - Train a dedicated `Explorer_ML_Model` (family `explorer`) on Sensor_Explorer component arrangement + per-component sensor readings (Req 5.1, 5.3); `classify(arrangement, readings)` returns a label and confidence (pure function)
    - Register with `model_registry`
    - _Affected files: `Backend/explorer_ml.py` (new)_
    - _Requirements: 5.1, 5.3_
  - [x]* 13.2 Write property test for explorer model classification validity
    - **Property 19: Explorer model classification validity**
    - **Validates: Requirements 5.2**
    - Assert the classification returns a valid label and confidence within `[0,1]`
    - _Affected files: `Backend/tests/properties/test_property_19.py` (new)_
  - [ ]* 13.3 Write property test for explorer feature-vector acceptance
    - **Property 20: Explorer feature-vector acceptance**
    - **Validates: Requirements 5.3**
    - Assert the model accepts arrangement + readings and produces a non-empty typed feature vector
    - _Affected files: `Backend/tests/properties/test_property_20.py` (new)_
  - [x] 13.4 Integrate ML into SensorExplorer.jsx (classify call, display, highlight)
    - After each `commitWorkspace`, POST the arrangement to `/explorer/history` and call `/explorer/classify`; display label + confidence + model version near the header (Req 5.4)
    - On an anomalous classification, set `highlightedInstanceIds` state and render contributing components with an emissive material (Req 5.5)
    - _Affected files: `frontend/src/components/SensorExplorer.jsx`_
    - _Requirements: 5.2, 5.4, 5.5_
  - [x] 13.5 Implement ExplorerHistory component and persistence hooks
    - Add an `ExplorerHistory` side panel listing entries in reverse-chronological order (Req 6.3) with a replay action that restores `placedComponents` from the stored arrangement (Req 6.4)
    - Persist a `workspace_state` entry on state change and a `classification` entry on each classification (Req 6.1, 6.2)
    - _Affected files: `frontend/src/components/SensorExplorer.jsx`, `frontend/src/components/ExplorerHistory.jsx` (new)_
    - _Requirements: 6.1, 6.2, 6.3, 6.4_
  - [ ]* 13.6 Write property test for explorer history persistence round-trip
    - **Property 21: Explorer history persistence round-trip**
    - **Validates: Requirements 6.1, 6.2**
    - _Affected files: `Backend/tests/properties/test_property_21.py` (new)_
  - [ ]* 13.7 Write frontend tests for explorer history replay
    - Assert selecting a history entry restores the recorded arrangement + classification
    - _Affected files: `frontend/src/components/__tests__/ExplorerHistory.test.jsx` (new)_
    - _Requirements: 6.3, 6.4_

- [x] 14. Frontend: control banner, ML status panel, sensors thresholds
  - [x] 14.1 Implement ControlSignalBanner component
    - Sit below the Navbar in `ProtectedLayout`; subscribe to `/stream/status` and show the current intent (SHUTDOWN/DE_RATE/RUN) alongside the System_Status (Req 3.7); turn red and show the alert on actuation-failure or fail-safe (Req 3.9, 11.4)
    - _Affected files: `frontend/src/components/ControlSignalBanner.jsx` (new), `frontend/src/App.jsx`_
    - _Requirements: 3.7, 3.9, 11.4_
  - [x] 14.2 Extend MLStatusPanel.jsx (version, recalibration timestamp, accuracy trend)
    - Fetch `/models/status` and `/models/trend/{family}`; render current model version, last recalibration timestamp, and a sparkline of the accuracy trend (Req 8.6, 14.1); keep `mlEngine.js` as the cold-start/local fallback
    - _Affected files: `frontend/src/components/MLStatusPanel.jsx`_
    - _Requirements: 8.6, 14.1_
  - [ ]* 14.3 Write frontend tests for control banner and ML status panel
    - Example/snapshot tests for banner rendering across intent states and ML panel metric display
    - _Affected files: `frontend/src/components/__tests__/ControlSignalBanner.test.jsx` (new)_
    - _Requirements: 3.7, 8.6, 14.1_

- [x] 15. Backend wiring and integration
  - [x] 15.1 Modify intelliwatch_brain.py to use inference.determine_status with cold-start fallback
    - `run_cycle` calls `inference.determine_status` first; the Welford engine is used only as the cold-start fallback when no trained model is active; `create_recommendations` consumes the `DetectionTrace` so recommendations stay traceable to inputs (Req 2.6)
    - _Affected files: `Backend/intelliwatch_brain.py`_
    - _Requirements: 2.6, 11.1_
  - [x] 15.2 Wire EquipmentController, IoT layer, and LearningSystem into server startup
    - Instantiate the controller, IoT layer, and scheduled recalibration at FastAPI startup; connect the controller's relay to the IoT layer and the controller's audit to `record_audit_entry`
    - _Affected files: `Backend/server.py`_
    - _Requirements: 3.1, 4.5, 8.3, 13.1_
  - [ ]* 15.3 Write integration tests (latency budgets, scalability, retention)
    - ≥100k-window training memory (Req 9.1), ≤100 ms inference timing (Req 9.3), ≥1M-row indexed query (Req 9.4), ≤200 ms status determination (Req 11.1), ≤500 ms SHUTDOWN dispatch (Req 3.5), ≤1 s fail-safe alert (Req 11.4), 365-day retention (Req 13.4), MQTT+HTTP protocol wiring (Req 4.3), heartbeat interval (Req 12.1)
    - _Affected files: `Backend/tests/test_integration.py` (new)_
    - _Requirements: 3.5, 4.3, 9.1, 9.3, 9.4, 11.1, 11.4, 12.1, 13.4_

- [ ] 16. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional tests and can be skipped for a faster MVP, though they are strongly recommended since they encode the 40 design correctness properties.
- Each task references specific requirements for traceability; requirements clauses map directly to `requirements.md`.
- Checkpoints (items 16) ensure incremental validation. Additional informal checkpoints are implied at the end of each epic.
- Property tests validate universal correctness properties; unit/integration tests validate specific examples, edge cases, and latency/scalability budgets.
- Implementation language is fixed by the codebase: Python (backend) and JavaScript/JSX (frontend). No language selection is needed.
- The existing Welford engine (`intelliwatch_engine.py`) and browser-side `mlEngine.js` are preserved as a cold-start fallback so the system degrades gracefully when no trained model is loaded.
- Schema migration is additive: the existing 7 tables are untouched; the 9 new tables are created idempotently.
- Each property-based test is written to its own dedicated test file (e.g. `test_property_11.py`) so that tests for the same module can run in parallel without file conflicts.
- Inference and control dispatch run in-process within the FastAPI server so the ≤200 ms status and ≤500 ms SHUTDOWN latency budgets are achievable without IPC overhead.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1", "3.1", "4.1", "8.1", "9.1"] },
    { "id": 1, "tasks": ["1.2", "2.2", "3.2", "4.2", "4.3", "5.1", "7.1", "8.2", "9.2", "9.3", "10.1", "11.1"] },
    { "id": 2, "tasks": ["2.3", "2.5", "4.4", "4.5", "5.2", "5.3", "7.2", "7.3", "7.4", "7.5", "8.3", "8.4", "8.5", "9.4", "10.2", "11.2", "13.1"] },
    { "id": 3, "tasks": ["2.4", "4.6", "4.7", "5.4", "7.6", "7.7", "7.8", "8.6", "8.7", "8.8", "8.9", "11.3", "11.4", "13.2", "13.3"] },
    { "id": 4, "tasks": ["4.8", "4.9", "5.5", "7.9", "7.10", "7.11", "8.10", "8.11", "8.12", "12.1"] },
    { "id": 5, "tasks": ["4.10", "4.11", "5.6", "14.1"] },
    { "id": 6, "tasks": ["4.12", "5.7", "5.8", "6.1"] },
    { "id": 7, "tasks": ["5.9", "5.10", "6.2", "10.3", "15.1"] },
    { "id": 8, "tasks": ["5.11", "10.4", "10.5", "10.6", "12.2"] },
    { "id": 9, "tasks": ["12.3", "14.2"] },
    { "id": 10, "tasks": ["12.4", "13.4"] },
    { "id": 11, "tasks": ["12.5", "13.5", "14.3"] },
    { "id": 12, "tasks": ["12.6", "13.6", "13.7", "15.2"] },
    { "id": 13, "tasks": ["15.3"] }
  ]
}
```
