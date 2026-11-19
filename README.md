# IntelliWatch
### Intelligent Condition Monitoring, Predictive Maintenance & Automated Safety-Actuation System

**IntelliWatch** is an end-to-end industrial equipment monitoring and intelligent safety-actuation system that integrates IoT, Machine Learning, real-time data processing, cloud infrastructure, and physical hardware control.

The system continuously monitors industrial equipment using multiple sensor inputs, including vibration, temperature, and electrical current. Its ML-based intelligence engine analyzes incoming sensor data, identifies abnormal operating conditions, classifies equipment health, and generates appropriate control decisions.

Based on the detected equipment condition, IntelliWatch can automatically execute safety responses such as normal operation, controlled de-rating, or emergency shutdown. These decisions are communicated through the IoT communication layer to physical relay channels and an LCD display, while sensor readings, alerts, device activity, and control actions are maintained in a persistent database.

The project combines edge-level hardware interaction with a cloud-hosted backend and a real-time web dashboard, providing an integrated approach to industrial condition monitoring, predictive maintenance, and automated equipment protection.

**Implementation Status:** All major project components and integrations have been implemented, including the frontend, backend, ML processing, database, authentication, IoT communication, control logic, and LCD-relay integration.

---

## 1. Project Overview

IntelliWatch addresses the limitations of conventional industrial monitoring systems, where equipment abnormalities may require manual observation and intervention.

Its objective is to move beyond passive monitoring by combining intelligent condition assessment with automated safety responses.

### Core Capabilities

- **Real-time condition monitoring:** Collects vibration, temperature, and current readings.
- **Machine Learning intelligence:** Analyzes sensor measurements and classifies equipment health.
- **Multi-level anomaly detection:** Identifies NORMAL, WARNING, and CRITICAL operating conditions.
- **Automated safety actuation:** Generates RUN, DE_RATE, and SHUTDOWN control decisions.
- **Physical hardware integration:** Interfaces with Raspberry Pi, multi-channel relays, and an HD44780 LCD.
- **Cloud deployment:** Runs the frontend and backend on separate cloud platforms.
- **Persistent data management:** Stores equipment readings, device information, alerts, and audit records.
- **Role-based access control:** Provides separate operational permissions for operators, maintenance engineers, and administrators.
- **Real-time visualization:** Displays equipment conditions, sensor readings, control signals, and alerts through a web dashboard.
- **Intelligent assistance:** Includes a chatbot and supporting equipment-information capabilities.

## 2. System Architecture

```text
       INDUSTRIAL EQUIPMENT
                |
                v
       SENSOR ACQUISITION
    Vibration | Temperature | Current
                |
                v
        RASPBERRY PI EDGE
                |
          HTTP / IoT
                |
                v
       RAILWAY BACKEND
                |
        IoT Communication
                |
                v
        ML INTELLIGENCE
                |
       Equipment Classification
                |
       NORMAL / WARNING / CRITICAL
                |
                v
      EQUIPMENT CONTROLLER
                |
       RUN / DE_RATE / SHUTDOWN
                |
          +-----+------+
          |            |
          v            v
      RELAY BOARD    LCD DISPLAY
          |            |
          v            v
    Physical Control  Live Status
          |
          v
      NEON POSTGRES
   Sensor Data / Audit / Records
          |
          v
      VERCEL FRONTEND
   Real-Time Monitoring Dashboard
```

### Three-Layer Architecture

**Layer 1 — Edge Hardware**

- Raspberry Pi-based sensor acquisition.
- Vibration, temperature, and current monitoring.
- HD44780 LCD with I2C communication.
- Multi-channel relay interface.
- Edge-to-cloud communication through HTTP/IoT adapters.

**Layer 2 — Backend Intelligence and Processing**

- Python 3.11 and FastAPI.
- IoT device registration and authentication.
- ML-based equipment condition classification.
- Automated control-decision generation.
- Relay and LCD actuator integration.
- Database operations and audit logging.
- JWT authentication and role-based authorization.
- WebSocket-based real-time communication.

**Layer 3 — Cloud Dashboard and Visualization**

- React 19 and Vite 8.
- Live sensor monitoring.
- Equipment condition and anomaly visualization.
- Control-signal notifications.
- Alert history.
- ML status information.
- Chatbot interface.
- User and device management.

## 3. Live Cloud Deployment

The application is deployed using separate cloud services for the frontend, backend, and database.

| Component | Platform | Deployment |
|---|---|---|
| Frontend | Vercel | Live |
| Backend | Railway | Live |
| Database | Neon PostgreSQL | Persistent |
| API | FastAPI | Cloud-hosted |
| Dashboard | React + Vite | Cloud-hosted |

### Deployment Links

- Frontend: https://frontend-alpha-tawny-49.vercel.app
- Backend: https://intelliwatch-backend-production.up.railway.app
- Health Check: https://intelliwatch-backend-production.up.railway.app/health
- Swagger API Documentation: https://intelliwatch-backend-production.up.railway.app/docs
- Neon Database Console: https://console.neon.tech/app/projects/gentle-snow-07661904

The production database contains 19 tables for application data and persistent records.

## 4. Backend Implementation

The backend is developed using FastAPI and Python.

| Component | Responsibility |
|---|---|
| `server.py` | Backend application and API orchestration |
| `iot_layer.py` | Device registration, authentication, validation, HTTP/MQTT adapters |
| `intelliwatch_brain.py` | ML inference and equipment health classification |
| `equipment_controller.py` | Control decisions, shutdown latching, dispatch, audit trail |
| `lcd_relay_module.py` | LCD and relay actuator integration |
| `database.py` | PostgreSQL/SQLite database abstraction |
| `auth.py` | Authentication and authorization |
| `learning_system.py` | Learning and model-support functionality |
| `vision_service.py` | Vision-related processing |
| `chatbot_api.py` | Chatbot backend functionality |

## 5. Machine Learning and Intelligent Decision-Making

The intelligence engine processes equipment sensor readings and identifies abnormal operating conditions.

### Equipment Health Classification

| Classification | Meaning | System Response |
|---|---|---|
| NORMAL | Equipment operating within configured limits | RUN |
| WARNING | Abnormal operating condition detected | DE_RATE |
| CRITICAL | Critical equipment condition detected | SHUTDOWN |

The system uses multiple sensor dimensions to support condition assessment rather than relying exclusively on a single measurement.

The classification output is passed to the equipment controller, which determines and dispatches the corresponding control intent.

## 6. Automated Equipment Safety and Actuation

A key feature of IntelliWatch is its ability to connect software-based anomaly detection with physical actuator control.

The equipment controller translates system decisions into actuator commands.

| Control Intent | Relay Behaviour | LCD Display |
|---|---|---|
| RUN | MAIN ON, INDICATOR ON | SYSTEM: RUN / STATUS: NORMAL |
| DE_RATE | MAIN + DE-RATE ON | SYSTEM: DERATE / STATUS: WARNING |
| SHUTDOWN | All channels OFF | SYSTEM: STOP / STATUS: CRITICAL |

### Safety Mechanisms

- Fail-safe relay initialization.
- De-energized relay state on startup.
- Critical shutdown latching.
- Software actuator shadow mode.
- Control-dispatch audit records.
- Device authentication and payload validation.
- Finite-value validation and payload-size limits.
- Optional hardware libraries for cross-platform backend compatibility.

Automated safety decisions operate through a system-level identity, independently of human dashboard interaction.

A physical emergency-stop circuit should remain independent of software control and be wired appropriately in series with the equipment safety circuit.

## 7. IoT Hardware Integration

The edge integration connects the Raspberry Pi to the existing backend IoT communication and control-dispatch architecture.

Hardware components:

- Raspberry Pi.
- Vibration sensor.
- Temperature sensor.
- Current sensor.
- HD44780 LCD with I2C interface.
- Multi-channel relay module.

The LCD-relay actuator is integrated through the `LCDRelayEdgeAdapter` and `create_lcd_relay_actuator` interfaces.

The device registers and authenticates with the IoT layer, enabling the existing control-signal delivery mechanism to communicate with the actuator.

### Communication Flow

1. Sensors acquire equipment measurements.
2. Raspberry Pi sends readings to the backend.
3. Backend validates device credentials and payload.
4. ML engine evaluates equipment condition.
5. Equipment controller generates the appropriate control intent.
6. IoT layer dispatches the control signal.
7. Relay channels and LCD respond to the command.
8. Database records relevant readings, events, and control activity.

## 8. Role-Based Access Control

IntelliWatch implements separate permissions for three operational roles.

| Capability | Operator | Maintenance Engineer | Admin |
|---|:---:|:---:|:---:|
| View sensor readings | Yes | Yes | Yes |
| View anomalies | Yes | Yes | Yes |
| Understand shutdown reasons | Yes | Yes | Yes |
| Dispatch control commands | No | Yes | Yes |
| Manage devices | No | No | Yes |
| Manage users | No | No | Yes |

Automated safety actuation is handled through the system identity rather than depending on the permissions of an individual logged-in user.

## 9. Database and Data Management

IntelliWatch uses a dual-database architecture:

- **Production:** Neon PostgreSQL.
- **Local development:** SQLite.

The production database currently contains 19 tables.

The database layer supports persistent application records, including equipment information, device data, sensor measurements, alerts, and control-related audit records.

## 10. Frontend and User Interface

The frontend is developed using React 19 and Vite 8.

Major interface capabilities include:

- Authentication and login interface.
- Live equipment sensor dashboard.
- Sensor status and anomaly visualization.
- Control-signal status banner.
- Alert and event history.
- ML status panel.
- Chatbot interface.
- Device and user management.
- Equipment visualization and 3D exploration.

The interface uses Recharts for data visualization and Three.js for 3D visualization.

## 11. Technology Stack

| Category | Technologies |
|---|---|
| Programming Language | Python 3.11, JavaScript |
| Backend | FastAPI |
| Frontend | React 19, Vite 8 |
| Machine Learning | Python ML ecosystem |
| Database | Neon PostgreSQL, SQLite |
| Communication | HTTP, WebSockets, MQTT adapters |
| Authentication | JWT, password hashing |
| Hardware | Raspberry Pi |
| Sensors | Vibration, Temperature, Current |
| Actuation | Multi-channel Relay |
| Display | HD44780 LCD, I2C |
| Visualization | Recharts, Three.js |
| Cloud Deployment | Railway, Vercel, Neon |
| Hardware Libraries | smbus2, RPi.GPIO |

## 12. Implementation Status

The major IntelliWatch development components have been implemented and integrated into the overall system.

| Project Component | Status |
|---|---|
| Frontend development | Implemented |
| Backend API development | Implemented |
| Authentication | Implemented |
| Role-based access control | Implemented |
| ML intelligence engine | Implemented |
| Anomaly classification | Implemented |
| Equipment control logic | Implemented |
| IoT communication layer | Implemented |
| LCD-relay actuator module | Implemented |
| Database integration | Implemented |
| Cloud backend deployment | Deployed |
| Cloud frontend deployment | Deployed |
| Persistent production database | Configured |
| Chatbot integration | Implemented |
| Hardware integration interfaces | Implemented |

**Overall Project Scope:** IntelliWatch combines software engineering, artificial intelligence, cloud computing, database management, IoT communication, and hardware actuation into one integrated industrial monitoring and safety system.

Implementation, deployment, integration, and physical validation are distinct milestones; actual hardware behaviour must be verified on the connected equipment before operational use.

## 13. Research Foundations

The project draws on published research and established approaches in predictive maintenance, industrial IoT, and ML-based anomaly detection.

1. Samatas et al. — *Predictive Maintenance: Bridging Artificial Intelligence and IoT*. [arXiv:2103.11148](https://arxiv.org/abs/2103.11148)

2. *Real-Time Adaptive Anomaly Detection in Industrial IoT Environments*. [arXiv:2601.03085](https://arxiv.org/abs/2601.03085)

3. Givnan et al. — *ML-Based Rotary Machine Fault Detection*. [arXiv:2110.01447](https://arxiv.org/abs/2110.01447)

4. IEEE Technology Navigator — *Machine Learning for Predictive Maintenance Using IoT Sensor Data*. [IEEE TechNav](https://technav.ieee.org/topic/predictive-maintenance)

5. *An Adaptable and Unsupervised TinyML Anomaly Detection System for Extreme Industrial Environments*. [MDPI Sensors, 2023](https://www.mdpi.com/1424-8220/23/4/2344)

6. Deshmukh and Dere — *AI-Driven Predictive Maintenance (Industry 4.0)*. [IJCRT:2401033](https://ijcrt.org/papers/IJCRT2401033.pdf)

## 14. Source Code and Project Repositories

| Repository | Purpose |
|---|---|
| [Miniproject5](https://github.com/LakshmiNarayana124/Miniproject5) | Project repository |
| [IntelliWatch-Private](https://github.com/LakshmiNarayana124/IntelliWatch-Private) | Main private development repository |

### Development Branches

| Branch | Purpose |
|---|---|
| `main` | Main integrated source |
| `clean-start` | Production deployment branch |
| `feature/iot-lcd-relay-integration` | LCD and relay integration |

---

## Final Project Summary

**IntelliWatch — Software + AI + IoT + Cloud + Physical Hardware.**

IntelliWatch demonstrates an integrated industrial condition-monitoring architecture that connects multi-sensor data acquisition, ML-based equipment health assessment, automated safety decisions, physical actuator interfaces, persistent cloud storage, and real-time visualization.

Rather than functioning as a conventional sensor-monitoring dashboard, the system is designed to close the loop between detecting an abnormal condition and initiating an appropriate equipment-control response.

Its architecture brings together edge computing, intelligent decision-making, cloud-based infrastructure, and hardware-level interaction within a single project.

**Project Objective:** To develop an intelligent, connected, and safety-oriented equipment monitoring system that supports condition-based maintenance and automated responses to abnormal industrial operating conditions.

*IntelliWatch — From Sensor Intelligence to Automated Equipment Protection.*
