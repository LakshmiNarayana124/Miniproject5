
# 👁️ IntelliWatch

> **Real-Time Industrial Machine Health Monitoring & Decision Support System**
>
> Raspberry Pi sensors → FastAPI backend → ML anomaly detection → live cloud dashboard.

IntelliWatch is an industrial machine-health monitoring prototype designed to identify abnormal equipment behaviour using vibration, temperature, and current signals. It combines sensor acquisition, machine-learning analysis, real-time visualization, role-based access, and maintenance decision support.

The project is designed to support predictive-maintenance workflows while remaining budget-friendly and suitable for Raspberry Pi-based deployment.

---

## ⚡ Quick Access

| Resource | Link |
|---|---|
| **Live Dashboard** | https://intelliwatch-cyan.vercel.app |
| **Backend API** | https://intelliwatch-backend.onrender.com |
| **API Documentation (Swagger)** | https://intelliwatch-backend.onrender.com/docs |
| **Registration Status** | https://intelliwatch-backend.onrender.com/auth/registration-status |
| **GitHub – IntelliWatch** | https://github.com/LakshmiNarayana124/IntelliWatch-Private |
| **GitHub – Backend/Deployment Source** | https://github.com/LakshmiNarayana124/Miniproject5 |
| **KAIST Bearing Dataset** | https://github.com/KAIST-VCLAB/KAIST-Bearing |
| **Vercel Dashboard** | https://vercel.com/dashboard |
| **Render Dashboard** | https://dashboard.render.com |
| **Neon PostgreSQL Console** | https://console.neon.tech |
| **Firebase Console** | https://console.firebase.google.com |

> Render Free instances may sleep after inactivity. The first request after sleeping can take around 50 seconds or longer. The frontend can remain deployed while the backend wakes up.

---

## 🎯 Project Overview

Industrial machines can develop faults such as bearing wear, imbalance, misalignment, looseness, overheating, and abnormal electrical loading.

Traditional maintenance often relies on scheduled inspections or manual observation. IntelliWatch explores a data-driven approach by continuously monitoring machine parameters and identifying deviations from expected behaviour.

### Objectives

- Monitor machine vibration, temperature, and current.
- Detect abnormal patterns using machine-learning models.
- Classify equipment condition into Normal, Warning, and Critical states.
- Visualize live sensor readings and historical trends.
- Provide alerts and maintenance-oriented decision support.
- Support role-based access for administrators, operators, and maintenance engineers.
- Provide a simulation mode for testing without physical sensors.
- Develop a low-cost Raspberry Pi-compatible IoT monitoring architecture.

### Project Scope

IntelliWatch is an academic industrial-monitoring prototype and decision-support system. Its predictions and Remaining Useful Life estimates are intended for experimentation and maintenance assistance, not as a certified safety controller or guaranteed industrial failure prediction.

---

## 🏗️ System Architecture

```text
              INDUSTRIAL EQUIPMENT
                       │
                       ▼
             Raspberry Pi 3B
                       │
       ┌───────────────┼────────────────┐
       │               │                │
       ▼               ▼                ▼
    ADXL345         DS18B20          ACS712
   Vibration      Temperature       Current
       │               │                │
       └───────────────┼────────────────┘
                       │
                       ▼
              Sensor Acquisition
             sensor_reader.py
                       │
                MQTT / HTTP
                       │
                       ▼
              FastAPI Backend
                (Render)
                       │
       ┌───────────────┼────────────────┐
       │               │                │
       ▼               ▼                ▼
   ML Engine       Authentication     Database
 XGBoost / IF /    JWT / Firebase    Neon PostgreSQL
   ONNX GRU          / RBAC          or configured DB
       │               │                │
       └───────────────┼────────────────┘
                       │
                 WebSocket API
                       │
                       ▼
              React Dashboard
                 (Vercel)
                       │
       ┌───────────────┼────────────────┐
       │               │                │
       ▼               ▼                ▼
 Live Sensor       Alert Log        3D Explorer
   Cards          Fault Panel       Equipment View
                       │
                       ▼
              Maintenance Insights
```

### Data Flow

1. Sensors acquire vibration, temperature, and current measurements.
2. The Raspberry Pi or simulation layer produces sensor readings.
3. Readings are transmitted to the backend through the configured communication layer.
4. The backend processes readings and evaluates machine condition.
5. ML models and anomaly-detection components contribute to fault analysis.
6. The backend stores relevant records and exposes API/WebSocket endpoints.
7. The frontend displays live readings, alerts, historical trends, and equipment information.

### Deployment Architecture

| Component | Platform | Purpose |
|---|---|---|
| Frontend | Vercel | React application and static assets |
| Backend | Render | FastAPI application and API |
| Database | Neon PostgreSQL / configured database | Persistent application data |
| Authentication | Firebase + backend authentication | Authentication and role validation |
| ML Runtime | Backend | Fault analysis and anomaly detection |
| Hardware | Raspberry Pi 3B | Sensor acquisition and IoT interface |

**Hosting cost target:** Free-tier deployment using Vercel Hobby, Render Free, Neon Free, and Firebase Spark where applicable. Free-tier availability, quotas, and service limits may change.

---

## 🧠 Machine Learning & Fault Analysis

IntelliWatch combines supervised classification and anomaly-detection approaches to analyze machine-health signals.

### ML Components

| Model / Component | Purpose |
|---|---|
| **XGBoost** | Fault classification using extracted sensor features |
| **Isolation Forest** | Unsupervised anomaly detection |
| **ONNX GRU** | Sequence-based anomaly analysis |
| **Scikit-learn Pipeline** | Feature processing, extraction, and scaling |

### Fault Categories

The system is designed to evaluate fault patterns including:

- Bearing wear
- Imbalance
- Thermal overload
- Electrical overload
- Misalignment
- Mechanical looseness
- Compound or multiple faults

### Condition Assessment

The analysis can map sensor and model outputs into condition categories:

| State | Meaning |
|---|---|
| **Normal** | Readings are within the configured expected range |
| **Warning** | An abnormal condition or developing fault pattern is detected |
| **Critical** | A severe condition requires attention |

Vibration assessment is informed by ISO 10816-3 / related vibration-severity guidance, subject to the applicable machine class, installation, and measurement conditions.

### Remaining Useful Life (RUL)

The project includes a Remaining Useful Life-oriented estimation interface with condition labels such as:

- Stable
- Warning
- Soon
- Imminent

These labels are maintenance-oriented estimates and should not be interpreted as guaranteed remaining operating time without validated degradation data and machine-specific calibration.

---

## 📊 Dashboard Pages

| Route | Description |
|---|---|
| `/` | Live sensor cards, ML fault panel, and alert log |
| `/vibration` | Vibration history and severity-zone visualization |
| `/temperature` | Temperature history and anomaly indicators |
| `/current` | Current draw and electrical fault patterns |
| `/explorer` | 3D equipment model and component exploration |
| `/vision` | Equipment image inspection using the configured Gemini AI integration |
| `/about` | Project overview, standards, and team information |
| `/admin/users` | User management for authorized administrators |

The dashboard also includes multilingual interface support, a chatbot interface, sensor status indicators, and responsive UI components.

---

## 🔐 Authentication & Roles

IntelliWatch supports backend authentication and role-based access.

### Login Methods

| Method | Description |
|---|---|
| **Username + Password** | Backend-authenticated login |
| **Google Sign-In** | Firebase authentication |
| **Phone OTP** | Firebase phone authentication; provider plan and configuration requirements apply |
| **Offline Demo** | Local demonstration session using synthetic data |

### User Roles

| Role | Intended Access |
|---|---|
| **ADMIN** | Administration and authorized system controls |
| **OPERATOR** | Equipment monitoring and operational dashboard |
| **MAINTENANCE_ENGINEER** | Maintenance analysis and authorized equipment actions |

The backend validates authorization for protected operations. Selecting a role in the frontend does not by itself grant backend permissions.

> Do not publish real passwords, API keys, Firebase private credentials, JWT secrets, or database connection strings in this README.

---

## 🗂️ Important Project Files

### Backend

| File / Directory | Responsibility |
|---|---|
| `Backend/server.py` | FastAPI application, API routes, middleware, and service initialization |
| `Backend/auth.py` | Authentication, token handling, and access-control logic |
| `Backend/intelliwatch_engine.py` | Core machine-health business logic and analysis |
| `Backend/sensor_config.py` | Sensor settings, configuration, and thresholds |
| `Backend/sensor_reader.py` | Sensor acquisition and simulation-mode readings |
| `Backend/equipment_controller.py` | Equipment-control logic and authorized actuation interface |
| `Backend/iot_layer.py` | IoT communication and hardware integration layer |
| `Backend/learning_system.py` | Learning and model-related functionality |
| `Backend/calibration.py` | Sensor and threshold calibration functionality |
| `Backend/obs_service.py` | Observability and service-related functionality |
| `Backend/explorer_ml.py` | ML functionality supporting the equipment explorer |
| `Backend/requirements.txt` | Python dependencies |
| `Backend/.env` | Local environment configuration; never commit secrets |

### Frontend

| File / Directory | Responsibility |
|---|---|
| `frontend/src/App.jsx` | Main application structure and routing |
| `frontend/src/App.css` | Application-level styling |
| `frontend/src/index.css` | Global styles |
| `frontend/src/main.jsx` | React entry point |
| `frontend/src/sensors.js` | Sensor-related frontend utilities |
| `frontend/src/components/LoginPage.jsx` | Login and authentication interface |
| `frontend/src/components/Navbar.jsx` | Navigation and status UI |
| `frontend/src/components/SensorPage.jsx` | Sensor visualization pages |
| `frontend/src/components/AlertLog.jsx` | Alert history interface |
| `frontend/src/components/Chatbot.jsx` | Chatbot UI |
| `frontend/src/components/TenderLeaderboard.jsx` | Leaderboard component |
| `frontend/src/components/AboutPage.jsx` | About and project information |
| `frontend/src/i18n.js` | Multilingual translation resources |
| `frontend/src/useLang.js` | Language-related hook |
| `frontend/src/useSensorData.js` | Sensor data handling hook |
| `frontend/package.json` | Frontend dependencies and scripts |
| `frontend/vite.config.js` | Vite configuration |

> File paths may differ between development branches. Use the current repository tree as the source of truth if a file has been reorganized.

---

## 🔌 Hardware & Sensor Integration

### Hardware Components

| Component | Function | Interface |
|---|---|---|
| Raspberry Pi 3B | Edge computing and sensor interface | GPIO |
| ADXL345 | Vibration measurement | I2C |
| DS18B20 | Temperature measurement | 1-Wire |
| ACS712 | Current measurement | Analog output |
| ADS1115 | ADC for current-sensor signal | I2C |
| Relay module | Prototype equipment-control interface | GPIO / control circuit |

### Wiring Reference

| Sensor | Interface | Raspberry Pi Pins |
|---|---|---|
| ADXL345 | I2C | SDA = GPIO2, SCL = GPIO3 |
| DS18B20 | 1-Wire | GPIO4 |
| ADS1115 | I2C | SDA = GPIO2, SCL = GPIO3, address commonly `0x48` |

The ADXL345 and ADS1115 share the I2C bus when configured with compatible addresses.

> Hardware wiring and electrical safety must be verified before connecting sensors, relays, or equipment. Raspberry Pi GPIO is not designed to directly drive industrial loads.

### Simulation Mode

The backend currently supports simulation mode for development and cloud demonstration.

Simulation mode allows the dashboard and backend to be tested without physical sensor hardware. Live cloud sensor readings should not be described as physical measurements unless the hardware acquisition path is actually connected and verified.

---

## 🚀 Run Locally

### Requirements

- Python 3.11
- Node.js 22 recommended
- Git
- Windows PowerShell, Linux, or macOS terminal

### 1. Start the Backend

Open a terminal:

```powershell
cd Backend

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

Create a local `Backend\.env` file containing the required configuration:

```env
INTELLIWATCH_SECRET_KEY=replace_with_a_secure_random_secret
DATABASE_URL=your_database_connection_string
INTELLIWATCH_CORS_ORIGINS=http://localhost:5173
FIREBASE_PROJECT_ID=intelliwatch-66ad0
```

Do not use the example secret in a real deployment.

Start the backend:

```powershell
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

Backend local URLs:

- API: http://localhost:8000
- Swagger documentation: http://localhost:8000/docs

### 2. Start the Frontend

Open a second terminal:

```powershell
cd frontend
npm install
```

Create `frontend\.env.local` with the backend URL and required Firebase web configuration variables:

```env
VITE_API_URL=http://localhost:8000
```

Add the Firebase configuration values required by the frontend. Keep private service-account credentials out of the frontend.

Start Vite:

```powershell
npm run dev
```

Open:

http://localhost:5173

---

## ☁️ Production Deployment

### Frontend – Vercel

Production frontend:

https://intelliwatch-cyan.vercel.app

Required environment variable:

```env
VITE_API_URL=https://intelliwatch-backend.onrender.com
```

Configure the variable for the Production environment in Vercel. Firebase web configuration variables must also be configured where required.

Vite environment variables are embedded during the build. After changing them, create a new frontend deployment.

### Backend – Render

Backend service:

https://intelliwatch-backend.onrender.com

Typical startup command:

```bash
uvicorn server:app --host 0.0.0.0 --port $PORT
```

Important environment variables include:

```env
INTELLIWATCH_SECRET_KEY
DATABASE_URL
INTELLIWATCH_CORS_ORIGINS
FIREBASE_PROJECT_ID
```

Set these in Render's Environment settings. Do not commit production secrets to GitHub.

### CORS Configuration

The backend must allow the production frontend origin.

```env
INTELLIWATCH_CORS_ORIGINS=https://intelliwatch-cyan.vercel.app
```

If additional origins are already configured, preserve them and separate each origin with a comma.

Examples of development origins:

```text
http://localhost:5173
http://127.0.0.1:5173
```

Do not add a path such as `/docs` or a trailing slash to the production origin.

### Deployment Verification

After deployment, verify:

1. Vercel deployment status is **Ready**.
2. Render service status is **Live**.
3. The registration-status endpoint returns valid JSON.
4. The frontend can reach the backend without a CORS error.
5. Login and role-based access work as expected.

Registration-status endpoint:

https://intelliwatch-backend.onrender.com/auth/registration-status

Expected response format:

```json
{
  "registration_enabled": true
}
```

The actual value depends on backend configuration.

---

## 🧪 Testing & Troubleshooting

### Backend health check

Open:

https://intelliwatch-backend.onrender.com/auth/registration-status

If it responds with JSON, the endpoint is reachable.

### If the login page shows an offline warning

- Wait for the Render Free instance to wake up.
- Hard refresh the website using `Ctrl + Shift + R`.
- Check that browser DevTools Offline mode is disabled.
- Check the browser Network tab for CORS errors.
- Verify the `access-control-allow-origin` response header matches the Vercel production origin.

### If a Vercel deployment fails

- Open Vercel → Deployments.
- Inspect the failed deployment's Build Logs.
- Restore the last successful production deployment if necessary.
- Diagnose the failed build separately before deploying again.

A failed new deployment does not necessarily remove the currently working production deployment.

---

## 📚 Research Basis

The project draws on established research in bearing-fault detection, anomaly detection, gradient boosting, and recurrent neural networks.

### 1. Explainable AI for Bearing Fault Detection

**Decker, Lebacher & Tresp (2023)** — *Does Your Model Think Like an Engineer? Explainable AI for Bearing Fault Detection with Deep Learning.*

IEEE ICASSP 2023.

This work informs the project's interest in interpretable fault classification and engineering-oriented feature analysis.

- [arXiv:2310.12967](https://arxiv.org/abs/2310.12967)
- [DOI](https://doi.org/10.1109/ICASSP49357.2023.10096396)

### 2. Physics-Informed Multimodal Bearing Fault Classification

**Alam et al. (2025)** — *Physics-Informed Multimodal Bearing Fault Classification under Variable Operating Conditions using Transfer Learning.*

This research motivates multimodal sensor analysis and cross-domain bearing-fault evaluation.

- [arXiv:2508.07536](https://arxiv.org/abs/2508.07536)

Reported benchmark results in research papers should not be treated as IntelliWatch's own validated accuracy.

### 3. Isolation Forest

**Liu et al. (2008)** — *Isolation Forest.*

IEEE International Conference on Data Mining.

The foundational research for the Isolation Forest unsupervised anomaly-detection approach.

- [DOI: 10.1109/ICDM.2008.17](https://doi.org/10.1109/ICDM.2008.17)

### 4. XGBoost

**Chen & Guestrin (2016)** — *XGBoost: A Scalable Tree Boosting System.*

ACM KDD 2016.

The research basis for the gradient-boosted tree classifier used in the project's ML stack.

- [arXiv:1603.02754](https://arxiv.org/abs/1603.02754)
- [DOI](https://doi.org/10.1145/2939672.2939785)

### 5. GRU Architecture

**Cho et al. (2014)** — *Learning Phrase Representations using RNN Encoder–Decoder for Statistical Machine Translation.*

EMNLP 2014.

This work introduces the GRU architecture used as the basis for sequence-modeling approaches.

- [arXiv:1406.1078](https://arxiv.org/abs/1406.1078)

### Dataset

The project uses the KAIST bearing-fault dataset as a research and development reference.

- [KAIST Bearing Dataset Repository](https://github.com/KAIST-VCLAB/KAIST-Bearing)

Dataset provenance, preprocessing, train/test separation, and evaluation metrics should be documented when reporting model performance.

---

## 📐 Standards & Engineering References

| Standard | Relevance |
|---|---|
| ISO 10816-3 | Mechanical vibration evaluation of machine vibration |
| ISO 13373-1 | Condition monitoring and vibration diagnostics |
| ISO 13381-1 | Prognostics and Remaining Useful Life concepts |
| IEC 60034-1 | Rotating electrical machine ratings and performance |
| IEC 62443 | Industrial automation and control system cybersecurity |

Standards are used as engineering references. Actual compliance or safety certification requires appropriate testing, machine-specific applicability assessment, and formal verification.

---

## 🛠️ Technology Stack

### Frontend

- React
- Vite
- React Router
- Recharts
- Three.js
- Firebase JavaScript SDK
- Progressive Web App capabilities

### Backend

- FastAPI
- Uvicorn
- Scikit-learn
- XGBoost
- ONNX Runtime
- Argon2
- PyJWT
- PostgreSQL / psycopg2
- Paho MQTT
- Google GenAI

### Infrastructure

- Vercel
- Render
- Neon PostgreSQL
- Firebase

---

## 🔭 Future Development

- Complete physical Raspberry Pi sensor integration.
- Validate sensor calibration and machine-specific thresholds.
- Expand IoT connectivity and deployment options.
- Improve mobile and cloud accessibility.
- Strengthen historical analysis and maintenance Q&A.
- Evaluate model performance using reproducible test datasets.
- Improve production monitoring, security, and reliability.

---

## 📄 License

MIT
