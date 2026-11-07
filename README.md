# IntelliWatch

### Real-Time Anomaly Detection & Decision Support System

**Monitor. Analyse. Detect. Decide.**

IntelliWatch is an industrial IoT monitoring and decision-support platform designed to analyse machine sensor data, identify unusual operating behaviour, and provide actionable maintenance insights.

It combines real-time sensor monitoring, a Python-based intelligence engine, persistent data storage, and an interactive web dashboard.

## Key Features

- **Real-Time Monitoring:** Vibration, temperature, and current monitoring.
- **Anomaly Detection:** Sensor analysis using statistical and knowledge-based techniques.
- **Decision Support:** Machine-condition assessment and recommended actions.
- **Historical Persistence:** SQLite-based storage for readings and assessments.
- **Interactive Dashboard:** Sensor visualizations and monitoring pages.
- **3D Hardware Explorer:** Interactive learning experience for sensor components.
- **Multilingual Interface:** Language support in the frontend.

## Technology Stack

| Layer | Technologies |
|---|---|
| Frontend | React, Vite, JavaScript, CSS |
| Data Visualization | Recharts |
| 3D Explorer | Three.js, React Three Fiber, Drei |
| Backend | Python, FastAPI |
| Intelligence Engine | Python, Statistical and Knowledge-Based Analysis |
| Database | SQLite |
| Hardware Platform | Raspberry Pi |
| Sensors | ADXL345, DS18B20, ACS712, ADS1115 |

## System Architecture

```text
Physical Sensors
      |
      v
Raspberry Pi / Sensor Interface
      |
      v
Python Intelligence Engine
      |
      +---- Anomaly Analysis
      |
      +---- Decision Support
      |
      v
SQLite Database
      |
      v
FastAPI Backend
      |
      v
React Dashboard
```

*The physical sensor-to-Raspberry Pi integration and complete hardware-to-software validation remain planned integration work.*

## Development Progress

| Component | Status |
|---|---|
| React Dashboard | Implemented |
| Frontend Deployment | Completed |
| Interactive 3D Explorer | Implemented |
| Python Intelligence Engine | Implemented and tested |
| SQLite Persistence | Implemented and tested |
| FastAPI Backend | Implemented |
| Simulation-Based Testing | Performed |
| Physical Raspberry Pi Integration | Pending |
| End-to-End Hardware Validation | Pending |

## Hardware Components

| Component | Purpose |
|---|---|
| ADXL345 | Vibration measurement |
| DS18B20 | Temperature measurement |
| ACS712 | Current measurement |
| ADS1115 | Analog-to-digital conversion |
| Raspberry Pi | Hardware interface and processing |

## Running the Frontend

```bash
cd frontend
npm install
npm run dev
```

## Project Scope

IntelliWatch is being developed as a budget-conscious, equipment-independent monitoring and decision-support prototype. Actual equipment operating limits must be configured and validated for the specific machine being monitored.

## Future Integration

- Connect physical sensors to the Raspberry Pi.
- Complete hardware-to-backend integration.
- Validate readings against real operating conditions.
- Perform end-to-end testing with physical sensor data.

---

**IntelliWatch — Turning Industrial Sensor Data into Actionable Intelligence.**