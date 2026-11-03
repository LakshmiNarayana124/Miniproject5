# Requirements Document

## Introduction

IntelliWatch is a budget-friendly, equipment-independent IoT condition-monitoring system that acquires vibration, temperature, and electrical-current readings, classifies equipment health, and recommends corrective action. The platform currently relies on a heuristic statistical engine (Welford online mean/variance with Mahalanobis-like distance), a simulation-only sensor reader, a stub FastAPI server, and a browser-side lightweight anomaly scorer (`mlEngine.js`). The 3D Sensor Explorer is a drag-and-drop hardware visualizer with no machine-learning integration and no persisted history.

This feature, **AIML Predictive Maintenance**, upgrades IntelliWatch from heuristic thresholds to a trained, scalable, continuously-learning predictive-maintenance platform. It completes a production model-training pipeline over the KAIST bearing dataset, defines comprehensive data models covering every anomaly-detection logic, implements status-aware automatic equipment control (CRITICAL shuts equipment off, WARNING de-rates, NORMAL passes through), adds a graceful IoT hardware integration layer for edge-processing devices, trains dedicated ML models for the 3D Sensor Explorer, persists a 3D Sensor Explorer history log, aligns detection logic with ISO 10816/20816 and ISO 17359 best practices, and provides an adaptive learning loop that improves anomaly-detection accuracy over time.

The scope spans the Python backend (model training, persistence, control-signal dispatch, IoT abstraction) and the React frontend (3D Explorer ML, history log, status-driven control-signal display).

## Glossary

- **IntelliWatch_System**: The complete predictive-maintenance platform comprising the Python backend, the React frontend, the trained ML models, the persistence layer, and the IoT integration layer.
- **Backend_API**: The FastAPI server (`server.py`) and its endpoints that serve the frontend and external integrators.
- **Frontend_UI**: The React single-page application that displays sensor data, model status, and control signals.
- **Training_Pipeline**: The offline workflow that loads the KAIST dataset, extracts features, trains, validates, and persists AIML models.
- **Anomaly_Detection_Model**: A trained machine-learning model that classifies a sensor feature vector as Normal, Warning, or Critical and, where applicable, identifies the fault type. Candidate families include gradient-boosted trees (XGBoost/LightGBM), Isolation Forest, autoencoders, LSTM/GRU sequence models, and ensembles of these.
- **Feature_Extractor**: The module that computes derived monitoring features from raw sensor windows, including RMS, peak, variance, kurtosis, crest factor, and FFT frequency-band energy.
- **Equipment_Controller**: The subsystem that translates a system status into a physical equipment control signal and dispatches that signal to the connected hardware.
- **Control_Signal**: A command sent to equipment representing one of three actuation intents: SHUTDOWN (CRITICAL), DE_RATE (WARNING), or RUN (NORMAL).
- **IoT_Integration_Layer**: The abstraction layer that discovers, connects, and manages IoT edge devices, forwards their data, and relays control signals while letting the device perform its own computation.
- **Edge_Device**: An IoT-ready hardware unit that boots independently, performs on-device computation, and exchanges data and commands with the IntelliWatch_System over a supported protocol without the software performing the device's core computation.
- **Sensor_Explorer**: The 3D hardware visualizer component (`SensorExplorer.jsx`) that renders IntelliWatch hardware components in an interactive 3D workspace.
- **Explorer_ML_Model**: A machine-learning model dedicated to the Sensor_Explorer that operates on the 3D visualization data to classify component or arrangement health.
- **Explorer_History_Log**: The persisted timeline of Sensor_Explorer workspace states and ML classifications that supports later review.
- **Learning_System**: The adaptive component that ingests operator-verified feedback and recalibrates Anomaly_Detection_Model thresholds and parameters so that detection accuracy improves over time.
- **Monitoring_Parameter**: Any raw or derived quantity the system tracks, including vibration acceleration, vibration RMS, vibration peak, vibration kurtosis, vibration crest factor, FFT band energy, temperature, temperature mean, temperature rise rate, electrical current, current RMS, current mean, and current variation.
- **Fault_Type**: A labelled bearing defect category from the KAIST dataset: Normal, BPFI (ball-pass-frequency inner-race), BPFO (ball-pass-frequency outer-race), Misalignment, or Unbalance.
- **Load_Level**: The torque applied during a KAIST experiment: 0 Nm, 2 Nm, or 4 Nm.
- **Severity**: The magnitude gradation of a fault, such as the BPFI/BPFO depth codes (03, 10, 30), Misalignment levels (01, 03, 05), or Unbalance mass (0583 mg to 3318 mg).
- **System_Status**: The consolidated equipment health state, one of NORMAL, WARNING, or CRITICAL, determined by the most severe sensor or model output.
- **KAIST_Dataset**: The bearing-fault feature dataset located under `KAIST/features/`, split into vibration features and temperature/current features, organized by Fault_Type, Load_Level, and Severity.

## Requirements

### Requirement 1: Model Training Pipeline

**User Story:** As a maintenance engineer, I want best-in-class AIML models trained on large data volumes, so that anomaly detection is accurate and reliable across varied operating conditions.

#### Acceptance Criteria

1. THE Training_Pipeline SHALL load every KAIST_Dataset feature file covering all Fault_Type values (Normal, BPFI, BPFO, Misalignment, Unbalance), all Load_Level values (0 Nm, 2 Nm, 4 Nm), and all Severity values into a single unified training set.
2. THE Training_Pipeline SHALL train at least one gradient-boosted-tree Anomaly_Detection_Model (XGBoost or LightGBM) for tabular fault classification.
3. THE Training_Pipeline SHALL train at least one unsupervised Anomaly_Detection_Model (Isolation Forest or autoencoder) for anomaly detection on data without labels.
4. THE Training_Pipeline SHALL train at least one sequence Anomaly_Detection_Model (LSTM or GRU) to capture time-dependent patterns across consecutive feature windows.
5. THE Training_Pipeline SHALL combine multiple Anomaly_Detection_Model instances into an ensemble whose combined decision serves as the primary classifier.
6. THE Training_Pipeline SHALL persist each trained Anomaly_Detection_Model to disk with a version identifier, a training timestamp, and a recorded training dataset hash.
7. WHEN a Training_Pipeline run completes, THE Training_Pipeline SHALL emit a training report containing per-model accuracy, precision, recall, and F1 score measured on a held-out validation split.
8. WHEN the Training_Pipeline cannot allocate memory for a requested model, THEN THE Training_Pipeline SHALL log the resource error and fall back to a reduced-capacity configuration without aborting the run.

### Requirement 2: Comprehensive Anomaly-Detection Data Models

**User Story:** As a data scientist, I want comprehensive data models that cover every anomaly-detection logic and monitoring parameter, so that detection is consistent and all signals relate to the learning models and control signals.

#### Acceptance Criteria

1. THE Feature_Extractor SHALL compute, for every vibration window, the RMS, peak, variance, kurtosis, and crest factor of each acceleration axis.
2. THE Feature_Extractor SHALL compute, for every vibration window, FFT frequency-band energy across at least four defined bands.
3. THE Feature_Extractor SHALL compute, for every temperature window, the mean, minimum, maximum, and temperature-rise rate.
4. THE Feature_Extractor SHALL compute, for every current window, the RMS, mean, and variation of each phase.
5. THE IntelliWatch_System SHALL represent every Monitoring_Parameter as a versioned data model field that carries a name, a unit, a sensor source, and a timestamp.
6. THE IntelliWatch_System SHALL link each Anomaly_Detection_Model output to the Monitoring_Parameter values and the System_Status that produced it, so that every detection decision is traceable to its input signals and its resulting Control_Signal.
7. WHEN a Monitoring_Parameter value is missing from a window, THEN THE Feature_Extractor SHALL mark that derived feature as unavailable and exclude it from the model input without failing the whole window.

### Requirement 3: Status-Aware Equipment Control and Actuation

**User Story:** As an operator, I want the equipment to respond automatically to the system status like magic, so that CRITICAL conditions shut equipment off quickly to prevent damage, WARNING conditions slow it down, and NORMAL conditions let it run uninterrupted.

#### Acceptance Criteria

1. WHEN the System_Status transitions to CRITICAL, THE Equipment_Controller SHALL dispatch a SHUTDOWN Control_Signal to the connected equipment.
2. WHEN the System_Status transitions from CRITICAL to NORMAL, THE Equipment_Controller SHALL dispatch a RUN Control_Signal to restore equipment operation.
3. WHEN the System_Status transitions to WARNING, THE Equipment_Controller SHALL dispatch a DE_RATE Control_Signal that reduces equipment operating intensity.
4. WHEN the System_Status is NORMAL, THE Equipment_Controller SHALL dispatch no intervention Control_Signal and let the equipment run as usual.
5. THE Equipment_Controller SHALL dispatch a CRITICAL SHUTDOWN Control_Signal within 500 milliseconds of the System_Status being determined as CRITICAL.
6. THE Equipment_Controller SHALL assign the SHUTDOWN Control_Signal a higher priority than the DE_RATE and RUN Control_Signals.
7. THE IntelliWatch_System SHALL display the current Control_Signal intent (SHUTDOWN, DE_RATE, or RUN) on the Frontend_UI alongside the System_Status.
8. WHEN the equipment acknowledges a Control_Signal, THE Equipment_Controller SHALL record the acknowledgement timestamp and the resulting equipment state in the persistence layer.
9. WHEN the connected equipment does not acknowledge a SHUTDOWN Control_Signal within a configured timeout, THEN THE Equipment_Controller SHALL raise an actuation-failure alert on the Frontend_UI.

### Requirement 4: IoT Hardware Integration Layer

**User Story:** As an integrator, I want a graceful connection layer for IoT-ready hardware that boots and operates with the UI while doing its own computation, so that the software connects, displays, and controls without performing the device's core processing.

#### Acceptance Criteria

1. THE IoT_Integration_Layer SHALL expose a device abstraction interface that any Edge_Device implements for connection, data exchange, and command reception.
2. WHEN an Edge_Device connects, THE IoT_Integration_Layer SHALL perform a graceful boot handshake that verifies device identity, capability, and protocol compatibility.
3. THE IoT_Integration_Layer SHALL support at least two IoT communication protocols, including MQTT and HTTP.
4. WHILE an Edge_Device is connected, THE IoT_Integration_Layer SHALL receive device-computed data and forward it to the IntelliWatch_System without performing the device's on-device computation.
5. THE IoT_Integration_Layer SHALL relay Control_Signals from the Equipment_Controller to the connected Edge_Device over the device's active protocol.
6. WHEN an Edge_Device disconnects unexpectedly, THE IoT_Integration_Layer SHALL mark the device as offline, surface the status on the Frontend_UI, and retain the last known device state.
7. WHEN an Edge_Device reconnects after a disconnection, THE IoT_Integration_Layer SHALL re-establish the session and resume data and command exchange.
8. IF an Edge_Device reports an incompatible capability during handshake, THEN THE IoT_Integration_Layer SHALL reject the connection and log the incompatibility reason.

### Requirement 5: 3D Sensor Explorer Machine Learning

**User Story:** As an operator, I want dedicated ML models for the 3D Sensor Explorer, so that the 3D visualization is informed by learned intelligence rather than static display only.

#### Acceptance Criteria

1. THE Training_Pipeline SHALL train at least one Explorer_ML_Model that operates on Sensor_Explorer visualization data.
2. THE Sensor_Explorer SHALL apply the Explorer_ML_Model to the current 3D workspace state and display the resulting classification on the Frontend_UI.
3. THE Explorer_ML_Model SHALL accept the Sensor_Explorer component arrangement and per-component sensor readings as input features.
4. THE IntelliWatch_System SHALL display the Explorer_ML_Model output, confidence, and model version within the Sensor_Explorer view.
5. WHEN the Explorer_ML_Model classifies the workspace state as anomalous, THE Sensor_Explorer SHALL visually highlight the contributing components on the 3D canvas.

### Requirement 6: 3D Sensor Explorer History Log

**User Story:** As an operator, I want a persistent timeline of the 3D Sensor Explorer states, so that I can review workspace history and model classifications over time.

#### Acceptance Criteria

1. THE IntelliWatch_System SHALL persist every Sensor_Explorer workspace state change to the Explorer_History_Log with a timestamp, the component arrangement, and the active user.
2. THE IntelliWatch_System SHALL persist every Explorer_ML_Model classification to the Explorer_History_Log with a timestamp, the classification label, the confidence, and the model version.
3. THE Frontend_UI SHALL provide a history view within the Sensor_Explorer that lists Explorer_History_Log entries in reverse-chronological order.
4. WHEN a user selects an Explorer_History_Log entry, THE Frontend_UI SHALL render the recorded component arrangement and classification for that timestamp.
5. THE Explorer_History_Log SHALL retain at least 500 of the most recent entries.
6. WHEN the Explorer_History_Log reaches its retention limit, THE IntelliWatch_System SHALL evict the oldest entries and retain the most recent entries without manual intervention.

### Requirement 7: Industry Standards and Benchmarks Alignment

**User Story:** As a maintenance engineer, I want the detection logic aligned with best practices from reputed organizations, so that thresholds and interpretations follow recognized industry standards.

#### Acceptance Criteria

1. THE IntelliWatch_System SHALL apply ISO 10816 and ISO 20816 vibration severity zones to classify vibration Monitoring_Parameters into Normal, Warning, and Critical bands.
2. THE IntelliWatch_System SHALL apply ISO 17359 condition-monitoring guidance to structure the Monitoring_Parameter acquisition, analysis, and recommendation workflow.
3. THE IntelliWatch_System SHALL document, for each Monitoring_Parameter threshold, the standard or benchmark the threshold derives from.
4. WHEN a Monitoring_Parameter threshold cannot be mapped to a recognized standard, THEN THE IntelliWatch_System SHALL flag the threshold as equipment-specific and require operator confirmation before activation.

### Requirement 8: Intelligent Predictive Maintenance and Adaptive Learning

**User Story:** As a maintenance engineer, I want the system to learn over time, so that anomaly-detection accuracy continuously improves as more verified data accumulates.

#### Acceptance Criteria

1. THE Learning_System SHALL accept operator-verified labels that confirm or dismiss a recorded anomaly event for a Monitoring_Parameter window.
2. WHEN an operator-verified label is submitted, THE Learning_System SHALL store the label with the originating feature vector, the model version that produced the original decision, and the verification timestamp.
3. THE Learning_System SHALL recalibrate Anomaly_Detection_Model parameters using accumulated verified labels at a configurable interval.
4. WHEN the recalibrated Anomaly_Detection_Model achieves a higher validation F1 score than the active model, THE Learning_System SHALL promote the recalibrated model to active status and record the promotion.
5. THE IntelliWatch_System SHALL record an accuracy trend for each Anomaly_Detection_Model that tracks F1 score across recalibration events.
6. THE Frontend_UI SHALL display the current model version, the last recalibration timestamp, and the latest accuracy trend for each Anomaly_Detection_Model.

### Requirement 9: Scalability for Large Data Volumes

**User Story:** As a data scientist, I want the training and inference pipeline to handle large data volumes, so that the models remain performant as the dataset and live sensor history grow.

#### Acceptance Criteria

1. THE Training_Pipeline SHALL train Anomaly_Detection_Model instances on training sets containing at least 100,000 feature windows without exceeding available system memory.
2. WHEN a training set exceeds a configured batch size, THE Training_Pipeline SHALL process the data in mini-batches so that memory usage stays bounded.
3. THE IntelliWatch_System SHALL perform per-window inference for an Anomaly_Detection_Model within 100 milliseconds on the target deployment hardware.
4. THE persistence layer SHALL index Monitoring_Parameter readings by sensor name and timestamp to support historical queries over at least 1,000,000 stored readings.

### Requirement 10: Model Accuracy Targets

**User Story:** As a maintenance engineer, I want defined accuracy targets for the trained models, so that I can trust the anomaly-detection decisions before relying on them for equipment control.

#### Acceptance Criteria

1. THE tabular fault-classification Anomaly_Detection_Model SHALL achieve a validation accuracy of at least 0.92 across all Fault_Type values before it is promoted to active status.
2. THE unsupervised anomaly-detection Anomaly_Detection_Model SHALL achieve a validation F1 score of at least 0.90 on labelled anomaly and normal windows.
3. THE IntelliWatch_System SHALL maintain a false-alarm rate at or below 0.05 for promoted Anomaly_Detection_Model instances, measured on the held-out validation split.
4. WHEN a candidate Anomaly_Detection_Model fails to meet its accuracy target, THEN THE Training_Pipeline SHALL prevent that model from being promoted to active status and record the shortfall.

### Requirement 11: Low-Latency Critical Actuation Path

**User Story:** As an operator, I want the critical actuation path to be fast and reliable, so that equipment is protected from damage the moment a critical condition is detected.

#### Acceptance Criteria

1. THE IntelliWatch_System SHALL determine the System_Status from a complete sensor window within 200 milliseconds of the window closing.
2. THE Equipment_Controller SHALL transmit a CRITICAL SHUTDOWN Control_Signal with a delivery-retry mechanism that reattempts transmission on transient failure.
3. WHILE a CRITICAL condition persists, THE Equipment_Controller SHALL maintain the SHUTDOWN Control_Signal and SHALL NOT downgrade to DE_RATE or RUN until the System_Status returns to NORMAL.
4. IF the Control_Signal delivery channel is unavailable at the moment a CRITICAL condition is detected, THEN THE Equipment_Controller SHALL raise a fail-safe alert within 1 second and continue retrying delivery.

### Requirement 12: IoT Protocol Support and Reliability

**User Story:** As an integrator, I want robust IoT protocol support with reliable data delivery, so that live monitoring and control remain stable over imperfect networks.

#### Acceptance Criteria

1. THE IoT_Integration_Layer SHALL maintain a connection heartbeat with each connected Edge_Device at a configurable interval.
2. WHEN an Edge_Device heartbeat is not received within twice the configured interval, THE IoT_Integration_Layer SHALL mark the device as unresponsive and notify the Frontend_UI.
3. THE IoT_Integration_Layer SHALL queue outbound Control_Signals while an Edge_Device is temporarily disconnected and deliver them upon reconnection within a configurable queue-retention window.
4. THE IoT_Integration_Layer SHALL authenticate each Edge_Device connection using a device credential before accepting device data or relaying commands.
5. WHEN an IoT protocol message is malformed, THE IoT_Integration_Layer SHALL reject the message, log the rejection, and continue operating without dropping the device connection.

### Requirement 13: Data Integrity, Security, and Auditability

**User Story:** As an administrator, I want control actions and model changes audited and access restricted, so that safety-critical equipment control remains accountable and tamper-resistant.

#### Acceptance Criteria

1. THE IntelliWatch_System SHALL record an immutable audit entry for every Control_Signal dispatched, containing the timestamp, the System_Status, the Control_Signal intent, the target equipment, and the triggering Monitoring_Parameters.
2. THE IntelliWatch_System SHALL record an audit entry for every Anomaly_Detection_Model promotion and recalibration, containing the model version, the trigger, and the resulting accuracy metrics.
3. THE Equipment_Controller SHALL restrict SHUTDOWN and DE_RATE Control_Signal dispatch to authenticated Backend_API sessions that hold an authorized role.
4. THE IntelliWatch_System SHALL retain Monitoring_Parameter readings, anomaly events, and audit entries for at least 365 days.
5. WHEN an unauthenticated session attempts to dispatch a Control_Signal, THEN THE Backend_API SHALL reject the request and record the rejected attempt.

### Requirement 14: Observability of Model and System Health

**User Story:** As a maintenance engineer, I want visibility into model health and system status, so that I can detect degradation and intervene before detection quality drops.

#### Acceptance Criteria

1. THE Backend_API SHALL expose an endpoint that returns the active Anomaly_Detection_Model version, the last training timestamp, and the latest validation metrics.
2. THE Backend_API SHALL expose an endpoint that returns the current System_Status, the current Control_Signal intent, and the connected Edge_Device status.
3. THE IntelliWatch_System SHALL log every Training_Pipeline run, Anomaly_Detection_Model recalibration, and Learning_System feedback ingestion with a timestamp and outcome.
4. WHEN an Anomaly_Detection_Model validation metric falls more than 0.05 below its promotion threshold after deployment, THE IntelliWatch_System SHALL raise a model-degradation alert on the Frontend_UI.
