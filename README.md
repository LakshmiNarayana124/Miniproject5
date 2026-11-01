# React + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currentl
y, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and [`typescript-eslint`](https://typescript-eslint.io) in your project.

IntelliWatch
Beyond Monitoring. Towards Machine Intelligence.
Turning industrial sensor data into actionable insights through real-time analytics, intelligent anomaly detection and interactive 3D hardware exploration.Active Development
IoT + AI/ML
3D Sensor Explorer

# IntelliWatch
### Real-Time Anomaly Detection & Decision Support System

**Monitor. Analyse. Detect. Decide.**

IntelliWatch is an intelligent industrial monitoring platform that analyses machine parameters, identifies abnormal behaviour and supports maintenance decisions through sensor analytics, IoT and AI/ML.

## ✨ Key Features

- **Real-Time Monitoring:** Vibration, temperature and current monitoring with interactive dashboards.
- **Anomaly Detection:** Statistical and knowledge-based analysis of unusual sensor behaviour.
- **Decision Support:** Machine-condition evaluation, probable scenarios and recommended actions.
- **Historical Analysis:** SQLite-based observation and pattern persistence.
- **Interactive 3D Explorer:** Explore hardware components through interactive 3D models.
- **Sensor Labs:** Educational visualization of sensor working principles and hardware concepts.

## 🏗️ Technology Stack

| Layer | Technologies |
|---|---|
| Frontend | React, Vite, JavaScript, CSS |
| Visualization | Recharts |
| 3D Explorer | Three.js, React Three Fiber, Drei |
| Backend | Python, FastAPI |
| Intelligence | Python, Statistical Analysis, AI/ML |
| Database | SQLite |
| IoT | Raspberry Pi, I²C, 1-Wire |

## 🔬 Hardware Components

| Component | Purpose |
|---|---|
| ADXL345 | Vibration monitoring |
| DS18B20 | Temperature sensing |
| ACS712 | Current measurement |
| ADS1115 | Analog-to-digital conversion |
| Raspberry Pi | Hardware processing |

## 🌐 3D Sensor Explorer

An interactive 3D workspace featuring eight implemented component models:

- Raspberry Pi
- Breadboard
- ADXL345
- ACS712
- DS18B20
- ADS1115
- Relay Module
- LCD Display

Features include model selection, 3D rotation, zoom, component descriptions and pin information.

**Sensor Labs:** Planned interactive wiring, circuit demonstrations and scientific experiments.

## 🧠 Intelligence & AI/ML

The Python intelligence engine (`intelliwatch_engine.py`) provides:

- Sensor-wise and combined analysis.
- Statistical and knowledge-based anomaly detection.
- Stability and trend evaluation.
- Historical pattern tracking.
- Decision-support logic.

**AI/ML Roadmap:** Isolation Forest integration, hybrid anomaly detection, model training and validation.

## ⚙️ System Architecture

```text
Sensors → Raspberry Pi → Python Engine
                            |
                     Anomaly Analysis
                            |
                      SQLite Database
                            |
                         FastAPI
                            |
                       React Dashboard
```

*End-to-end hardware and software integration is under development.*

## 🚀 Getting Started

**Frontend**
```bash
cd frontend
npm install
npm run dev
```

**Backend**
```bash
cd Backend
pip install -r requirements.txt
uvicorn server:app --reload
```

**Run Intelligence Engine**
```bash
python intelliwatch_engine.py
```

## 📊 Development Progress

| Module | Status |
|---|---|
| React Dashboard & Sensor Pages | Implemented |
| Frontend Deployment | Completed |
| 3D Sensor Explorer | Implemented |
| SQLite Initialization & Engine Persistence | Tested |
| Python Intelligence Engine | Implemented & Executed |
| FastAPI Foundation | Implemented |
| Isolation Forest | Pending |
| Sensor Labs & Circuit Experiments | In Progress |
| Raspberry Pi Hardware Integration | Pending |
| End-to-End Integration | Pending |

## 🔮 Upcoming Enhancements

- Complete backend and frontend integration.
- Connect physical sensors to Raspberry Pi.
- Integrate Isolation Forest into the intelligence engine.
- Develop interactive sensor experiments.
- Validate anomaly detection using actual machine data.

## 🛠️ Project Information

**Category:** Industrial IoT | AI/ML | Predictive Maintenance  
**Platform:** Raspberry Pi  
**Repository:** [IntelliWatch – GitHub](https://github.com/LakshmiNarayana124/Miniproject5)

---

### IntelliWatch
*Turning industrial sensor data into actionable intelligence.*
