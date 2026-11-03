
import { useState } from 'react'
import { t } from '../i18n'
import useLang from '../useLang'
import './AboutPage.css'

// ==================================================
// ABOUT / FAQ PAGE — IntelliWatch
// Covers objectives, purpose, protective stop/slowdown
// mechanism, and common questions from external
// predictive maintenance platforms.
// ==================================================

// ── Multilingual content blocks ───────────────────
const CONTENT = {
  hero_title: {
    en: 'About IntelliWatch',
    hi: 'IntelliWatch के बारे में',
    kn: 'IntelliWatch ಬಗ್ಗೆ',
    ta: 'IntelliWatch பற்றி',
    te: 'IntelliWatch గురించి',
  },
  hero_sub: {
    en: 'Real-time Anomaly Detection & Decision Support for Industrial Machinery',
    hi: 'औद्योगिक मशीनरी के लिए रियल-टाइम Anomaly Detection और Decision Support',
    kn: 'ಕೈಗಾರಿಕಾ ಯಂತ್ರಗಳಿಗಾಗಿ Real-time Anomaly Detection ಮತ್ತು Decision Support',
    ta: 'தொழில்துறை இயந்திரங்களுக்கான நேரடி முரண்பாடு கண்டறிதல் மற்றும் முடிவு ஆதரவு',
    te: 'పారిశ్రామిక యంత్రాల కోసం రియల్-టైమ్ అనామలీ డిటెక్షన్ మరియు నిర్ణయ మద్దతు',
  },

  // Sections
  sec_objective:   { en: '🎯 Objectives',              hi: '🎯 उद्देश्य',              kn: '🎯 ಉದ್ದೇಶಗಳು',             ta: '🎯 நோக்கங்கள்',              te: '🎯 లక్ష్యాలు'             },
  sec_how:         { en: '⚙️ How It Works',             hi: '⚙️ यह कैसे काम करता है',   kn: '⚙️ ಇದು ಹೇಗೆ ಕೆಲಸ ಮಾಡುತ್ತದೆ', ta: '⚙️ இது எவ்வாறு செயல்படுகிறது', te: '⚙️ ఇది ఎలా పని చేస్తుంది'   },
  sec_protection:  { en: '🛡️ Protective Action System', hi: '🛡️ सुरक्षात्मक कार्रवाई प्रणाली', kn: '🛡️ ರಕ್ಷಣಾ ಕ್ರಿಯಾ ವ್ಯವಸ್ಥೆ', ta: '🛡️ பாதுகாப்பு செயல் முறை',   te: '🛡️ రక్షణ చర్య వ్యవస్థ'     },
  sec_sensors:     { en: '📡 Monitored Sensors',        hi: '📡 निगरानी किए गए सेंसर',  kn: '📡 ಮೇಲ್ವಿಚಾರಣೆ Sensors',   ta: '📡 கண்காணிக்கப்படும் சென்சார்கள்', te: '📡 పర్యవేక్షించబడే సెన్సర్‌లు' },
  sec_faq:         { en: '❓ Frequently Asked Questions',hi: '❓ अक्सर पूछे जाने वाले प्रश्न', kn: '❓ ಪದೇ ಪದೇ ಕೇಳಲಾಗುವ ಪ್ರಶ್ನೆಗಳು', ta: '❓ அடிக்கடி கேட்கப்படும் கேள்விகள்', te: '❓ తరచూ అడిగే ప్రశ్నలు'   },
  sec_tech:        { en: '🧠 Technology Stack',         hi: '🧠 तकनीकी स्टैक',           kn: '🧠 ತಂತ್ರಜ್ಞಾನ Stack',        ta: '🧠 தொழில்நுட்ப அடுக்கு',    te: '🧠 టెక్నాలజీ స్టాక్'         },
}

// Objectives list (always English + current lang)
const OBJECTIVES = {
  en: [
    'Continuously monitor industrial motor sensors — vibration, temperature, and current — in real time.',
    'Detect anomalies early using machine learning classifiers trained on the KAIST bearing fault dataset.',
    'Issue immediate equipment stop commands when critical thresholds are breached to prevent hardware damage.',
    'Gracefully reduce equipment speed when warning thresholds are reached, avoiding abrupt shutdowns.',
    'Provide maintenance engineers with clear, actionable recommendations ranked by fault severity.',
    'Support role-based access so operators, engineers, and admins see what is relevant to them.',
    'Work seamlessly on low-cost Raspberry Pi hardware connected to standard industrial sensors.',
  ],
  hi: [
    'रियल-टाइम में औद्योगिक मोटर सेंसर — कंपन, तापमान और करंट — की निरंतर निगरानी।',
    'KAIST bearing fault dataset पर प्रशिक्षित ML classifiers का उपयोग करके जल्दी anomaly पहचान।',
    'हार्डवेयर को नुकसान से बचाने के लिए critical threshold पार होने पर तत्काल उपकरण रोक आदेश।',
    'अचानक बंद होने से बचाने के लिए warning threshold पर उपकरण की गति धीरे-धीरे कम करना।',
    'maintenance engineers को fault की गंभीरता के अनुसार ranked recommendations प्रदान करना।',
    'Role-based access ताकि operators, engineers और admins को प्रासंगिक जानकारी मिले।',
    'कम लागत वाले Raspberry Pi hardware पर standard industrial sensors के साथ काम करना।',
  ],
  kn: [
    'ಕೈಗಾರಿಕಾ ಮೋಟರ್ sensors — ಕಂಪನ, ತಾಪಮಾನ, ವಿದ್ಯುತ್ — ನಿರಂತರ real-time ಮೇಲ್ವಿಚಾರಣೆ.',
    'KAIST bearing fault dataset ಮೇಲೆ ತರಬೇತಿ ಪಡೆದ ML classifiers ಮೂಲಕ anomaly ಮೊದಲೇ ಪತ್ತೆ.',
    'Critical threshold ಮೀರಿದಾಗ hardware ಹಾನಿ ತಡೆಯಲು ತಕ್ಷಣ ಉಪಕರಣ ನಿಲ್ಲಿಸುವ ಆದೇಶ.',
    'Warning threshold ಸಂದರ್ಭದಲ್ಲಿ ಹಠಾತ್ ಸ್ಥಗಿತ ತಪ್ಪಿಸಲು ಕ್ರಮೇಣ ವೇಗ ಕಡಿತ.',
    'Fault ತೀವ್ರತೆ ಆಧರಿಸಿ maintenance engineers ಗೆ ranked recommendations ನೀಡುವುದು.',
    'Role-based access ಮೂಲಕ operators, engineers ಮತ್ತು admins ಪ್ರಸ್ತುತ ಮಾಹಿತಿ ಪಡೆಯುತ್ತಾರೆ.',
    'Standard industrial sensors ಸಂಪರ್ಕಿತ ಕಡಿಮೆ ವೆಚ್ಚದ Raspberry Pi ನಲ್ಲಿ ನಿರ್ಮಿಸಲಾಗಿದೆ.',
  ],
  ta: [
    'தொழில்துறை மோட்டார் சென்சார்கள் — அதிர்வு, வெப்பநிலை, மின்னோட்டம் — நேரடியாக கண்காணிப்பு.',
    'KAIST bearing fault dataset இல் பயிற்சி பெற்ற ML classifiers மூலம் முரண்பாடு முன்கூட்டியே கண்டறிதல்.',
    'வன்பொருள் சேதத்தை தடுக்க critical threshold மீறும்போது உடனடி நிறுத்த கட்டளை.',
    'திடீர் நிறுத்தம் தவிர்க்க warning threshold-ல் படிப்படியான வேக குறைப்பு.',
    'பழுது தீவிரத்தை அடிப்படையாகக் கொண்ட ranked பராமரிப்பு பரிந்துரைகள்.',
    'Role-based access மூலம் operators, engineers மற்றும் admins தொடர்புடைய தகவலை பார்க்கலாம்.',
    'குறைந்த செலவு Raspberry Pi hardware மற்றும் standard சென்சார்களுடன் இயங்குகிறது.',
  ],
  te: [
    'పారిశ్రామిక మోటార్ సెన్సర్‌లు — కంపనం, ఉష్ణోగ్రత, కరెంట్ — నిరంతర రియల్-టైమ్ పర్యవేక్షణ.',
    'KAIST bearing fault dataset లో శిక్షణ పొందిన ML classifiers ద్వారా ముందుగా అనామలీ గుర్తింపు.',
    'హార్డ్‌వేర్ నష్టాన్ని నివారించడానికి critical threshold దాటినప్పుడు వెంటనే పరికరం ఆపు.',
    'ఆకస్మిక ఆపు లేకుండా warning threshold లో క్రమంగా వేగ తగ్గింపు.',
    'లోపం తీవ్రత ఆధారంగా ranked నిర్వహణ సిఫార్సులు.',
    'Role-based access ద్వారా operators, engineers మరియు admins సంబంధిత సమాచారాన్ని చూస్తారు.',
    'తక్కువ ధర Raspberry Pi హార్డ్‌వేర్ మరియు standard సెన్సర్‌లతో పని చేస్తుంది.',
  ],
}

const FAQ = {
  en: [
    {
      q: 'What faults can IntelliWatch detect?',
      a: 'IntelliWatch detects bearing faults (BPFI and BPFO), shaft misalignment, rotor unbalance, motor overload, overheating from poor lubrication, and general anomalies in current draw. The ML model is trained on KAIST bearing fault features.',
    },
    {
      q: 'What happens when a critical threshold is breached?',
      a: 'IntelliWatch immediately issues an equipment stop command to the connected relay via GPIO. This cuts power to the motor, preventing mechanical damage. The dashboard shows a pulsing red critical banner and the Alert Log records the event with a timestamp. Equipment must be manually cleared before restart.',
    },
    {
      q: 'How does the warning mode protect equipment?',
      a: 'At warning level, IntelliWatch does not stop the equipment abruptly. Instead, it signals a graceful speed reduction — reducing motor RPM incrementally over several seconds. This avoids shock loads and mechanical stress while bringing readings back into the normal range. If values continue to rise and cross the critical threshold, the full stop is then triggered.',
    },
    {
      q: 'Why is a gradual slowdown better than an immediate stop at warning level?',
      a: 'Abrupt stops under load cause mechanical shock, bearing wear, shaft stress, and winding surge in electric motors. A smooth ramp-down preserves component life and allows operators time to inspect the machine before it reaches a dangerous state. Industry standards (ISO 13381, IEC 60034) recommend controlled shutdown procedures for exactly this reason.',
    },
    {
      q: 'Can IntelliWatch integrate with existing SCADA or PLC systems?',
      a: 'Yes. The backend exposes a REST API and supports WebSocket or MQTT data streams. SCADA systems can push sensor data to IntelliWatch via MQTT and receive anomaly events as JSON payloads. PLC integration is possible through OPC-UA adapters or direct GPIO bridges on the Raspberry Pi.',
    },
    {
      q: 'What sensors does IntelliWatch support?',
      a: 'IntelliWatch currently monitors the ADXL345 accelerometer (vibration), DS18B20 temperature probe (temperature), and ACS712 Hall-effect sensor (current). The ADS1115 ADC converts the ACS712 analog output to digital. The system is extensible — additional I²C or SPI sensors can be added through the sensor configuration module.',
    },
    {
      q: 'How accurate is the anomaly detection?',
      a: 'The ML classifier is trained on the KAIST bearing fault dataset which covers BPFI, BPFO, misalignment, and unbalance at 0 Nm, 2 Nm, and 4 Nm load conditions. Cross-validation accuracy on the test split exceeds 95% for the feature-engineered dataset. Real-world accuracy depends on sensor placement, motor type, and operating conditions.',
    },
    {
      q: 'Is the system safe if the IoT hardware disconnects mid-run?',
      a: 'Yes. IntelliWatch treats a missing signal as an uncertain state and does not falsely trigger stop commands. The dashboard displays "Awaiting IoT Signal" gracefully. If reconnection is detected, monitoring resumes automatically. The relay defaults to a safe off-state (normally open) if the Raspberry Pi loses power.',
    },
    {
      q: 'How are user roles structured?',
      a: 'Three roles: ADMIN can manage users and view everything. OPERATOR can view all dashboards and acknowledge alerts. MAINTENANCE ENGINEER can view sensor data, access the recommendation engine, and run diagnostics. Passwords are hashed with Argon2 and all API calls require a JWT bearer token.',
    },
    {
      q: 'How does IntelliWatch compare to platforms like SKF IMx, Emerson AMS, or Fluke?',
      a: 'IntelliWatch is an open-source, edge-first system designed for low-cost deployment on commodity hardware. Commercial platforms like SKF IMx use proprietary sensor nodes and cloud analytics at much higher cost. IntelliWatch offers comparable real-time monitoring and ML-based fault classification with full control of data, on-premise processing, and no vendor lock-in.',
    },
    {
      q: 'What is the TenderWatch Leaderboard?',
      a: 'TenderWatch tracks and ranks industrial organizations by their predictive maintenance maturity score — a composite of monitored asset coverage, system uptime, and anomaly response time. It is intended to benchmark and motivate adoption of proactive maintenance practices across industry sectors.',
    },
    {
      q: 'Does IntelliWatch support multiple machines simultaneously?',
      a: 'The current architecture is designed for single-machine monitoring per Raspberry Pi node. Multi-machine support is on the roadmap — each node would push data to a central IntelliWatch hub that aggregates readings and runs fleet-level anomaly detection.',
    },
  ],

  hi: [
    { q: 'IntelliWatch कौन सी खराबियाँ पकड़ सकता है?', a: 'IntelliWatch bearing faults (BPFI और BPFO), shaft misalignment, rotor unbalance, motor overload, और poor lubrication से overheating पकड़ता है। ML model KAIST dataset पर trained है।' },
    { q: 'Critical threshold पार होने पर क्या होता है?', a: 'IntelliWatch तुरंत GPIO relay को stop command देता है, जिससे motor की power कट हो जाती है। Dashboard पर pulsing red banner दिखता है और Alert Log में event record होता है। Restart से पहले manual inspection जरूरी है।' },
    { q: 'Warning mode में equipment कैसे सुरक्षित होती है?', a: 'Warning पर IntelliWatch अचानक नहीं रोकता — motor RPM कई seconds में धीरे-धीरे कम करता है। अगर values critical तक पहुँचती हैं तभी पूरी तरह रोका जाता है।' },
    { q: 'Warning पर gradual slowdown immediate stop से बेहतर क्यों है?', a: 'अचानक रोकने से mechanical shock, bearing wear और winding surge होती है। Smooth ramp-down से component life बचती है और operators को inspect करने का समय मिलता है।' },
    { q: 'क्या IntelliWatch SCADA/PLC से integrate हो सकता है?', a: 'हाँ। Backend REST API, WebSocket और MQTT support करता है। SCADA MQTT से data push कर सकता है और JSON format में anomaly events receive कर सकता है।' },
    { q: 'Anomaly detection कितनी accurate है?', a: 'KAIST dataset पर ML classifier की accuracy 95%+ है। Real-world accuracy sensor placement और operating conditions पर निर्भर करती है।' },
    { q: 'IoT hardware disconnect होने पर क्या होता है?', a: 'Missing signal को uncertain state माना जाता है। Dashboard "Awaiting IoT Signal" दिखाता है। Relay default safe off-state में रहता है।' },
    { q: 'User roles कैसे काम करते हैं?', a: 'ADMIN सब manage कर सकता है। OPERATOR dashboard देख और alerts acknowledge कर सकता है। MAINTENANCE ENGINEER diagnostics चला सकता है। Passwords Argon2 से hash होते हैं।' },
  ],

  kn: [
    { q: 'IntelliWatch ಯಾವ ದೋಷಗಳನ್ನು ಪತ್ತೆ ಮಾಡಬಹುದು?', a: 'BPFI, BPFO bearing faults, shaft misalignment, rotor unbalance, motor overload ಮತ್ತು overheating. ML model KAIST dataset ಮೇಲೆ trained.' },
    { q: 'Critical threshold ಮೀರಿದಾಗ ಏನಾಗುತ್ತದೆ?', a: 'IntelliWatch GPIO relay ಮೂಲಕ ತಕ್ಷಣ stop command ನೀಡುತ್ತದೆ. Dashboard ನಲ್ಲಿ pulsing red banner ಕಾಣಿಸಿಕೊಳ್ಳುತ್ತದೆ ಮತ್ತು Alert Log ನಲ್ಲಿ event ದಾಖಲಾಗುತ್ತದೆ.' },
    { q: 'Warning mode ನಲ್ಲಿ ಉಪಕರಣ ಹೇಗೆ ಸುರಕ್ಷಿತ?', a: 'Warning ನಲ್ಲಿ ಹಠಾತ್ ನಿಲ್ಲಿಸುವ ಬದಲು motor RPM ಕ್ರಮೇಣ ಕಡಿಮೆ ಮಾಡಲಾಗುತ್ತದೆ. Values critical ತಲುಪಿದಾಗ ಮಾತ್ರ ಪೂರ್ಣ stop.' },
    { q: 'SCADA/PLC ಜೊತೆ integrate ಮಾಡಬಹುದೇ?', a: 'ಹೌದು. Backend REST API, WebSocket ಮತ್ತು MQTT support ಮಾಡುತ್ತದೆ.' },
    { q: 'Anomaly detection ಎಷ್ಟು accurate?', a: 'KAIST dataset ನಲ್ಲಿ 95%+ accuracy. Real-world accuracy sensor placement ಮೇಲೆ ಅವಲಂಬಿಸಿದೆ.' },
    { q: 'User roles ಹೇಗೆ ಕೆಲಸ ಮಾಡುತ್ತವೆ?', a: 'ADMIN ಎಲ್ಲ manage ಮಾಡಬಹುದು. OPERATOR dashboard ನೋಡಬಹುದು. MAINTENANCE ENGINEER diagnostics ನಡೆಸಬಹುದು.' },
  ],

  ta: [
    { q: 'IntelliWatch என்ன கோளாறுகளை கண்டறியும்?', a: 'BPFI, BPFO bearing faults, shaft misalignment, rotor unbalance, motor overload மற்றும் overheating. ML model KAIST dataset இல் பயிற்சி பெற்றது.' },
    { q: 'Critical threshold மீறும்போது என்ன நடக்கும்?', a: 'IntelliWatch GPIO relay மூலம் உடனடி stop command பிறப்பிக்கிறது. Dashboard இல் pulsing red banner தெரியும், Alert Log இல் பதிவாகும்.' },
    { q: 'Warning mode இல் உபகரணம் எவ்வாறு பாதுகாக்கப்படுகிறது?', a: 'திடீர் நிறுத்தம் இல்லாமல் motor RPM படிப்படியாக குறைக்கப்படுகிறது. Values critical-ஐ அடைந்தால் மட்டுமே முழு நிறுத்தம்.' },
    { q: 'SCADA/PLC உடன் இணைக்கலாமா?', a: 'ஆம். Backend REST API, WebSocket மற்றும் MQTT ஆதரிக்கிறது.' },
    { q: 'Anomaly detection எவ்வளவு துல்லியமானது?', a: 'KAIST dataset இல் 95%+ accuracy. உண்மையான accuracy sensor வைப்பிடத்தை பொறுத்தது.' },
    { q: 'பயனர் roles எவ்வாறு செயல்படுகின்றன?', a: 'ADMIN அனைத்தையும் நிர்வகிக்கலாம். OPERATOR dashboard பார்க்கலாம். MAINTENANCE ENGINEER diagnostics இயக்கலாம்.' },
  ],

  te: [
    { q: 'IntelliWatch ఏ లోపాలను గుర్తిస్తుంది?', a: 'BPFI, BPFO bearing faults, shaft misalignment, rotor unbalance, motor overload మరియు overheating. ML model KAIST dataset లో శిక్షణ పొందింది.' },
    { q: 'Critical threshold దాటినప్పుడు ఏమి జరుగుతుంది?', a: 'IntelliWatch GPIO relay ద్వారా వెంటనే stop command ఇస్తుంది. Dashboard లో pulsing red banner కనిపిస్తుంది, Alert Log లో నమోదవుతుంది.' },
    { q: 'Warning mode లో పరికరం ఎలా రక్షించబడుతుంది?', a: 'ఆకస్మిక ఆపు లేకుండా motor RPM క్రమంగా తగ్గించబడుతుంది. Values critical కి చేరినప్పుడు మాత్రమే పూర్తి ఆపు.' },
    { q: 'SCADA/PLC తో ఇంటిగ్రేట్ చేయవచ్చా?', a: 'అవును. Backend REST API, WebSocket మరియు MQTT మద్దతు ఇస్తుంది.' },
    { q: 'Anomaly detection ఎంత accurate?', a: 'KAIST dataset లో 95%+ accuracy. నిజ-ప్రపంచ accuracy సెన్సర్ ప్లేస్‌మెంట్ పై ఆధారపడుతుంది.' },
    { q: 'User roles ఎలా పని చేస్తాయి?', a: 'ADMIN అన్నీ నిర్వహించగలరు. OPERATOR dashboard చూడగలరు. MAINTENANCE ENGINEER diagnostics నడుపుగలరు.' },
  ],
}

const SENSOR_TABLE = [
  // Thresholds per published standards:
  // Vibration: ISO 10816-3:2009 Group 2 (rigid mount, 15–75 kW)
  // Temperature: IEC 60034-1 Class F, 40 °C ambient
  // Current: IEC 60947-4-1 / NEMA MG-1 (7.5 kW, 415 V, In=15 A)
  { sensor: 'ADXL345',  type: 'Vibration',    protocol: 'I²C / SPI', range: '0 – 7.1 mm/s',   fault: 'Bearing (BPFI/BPFO), Misalignment, Unbalance', standard: 'ISO 10816-3' },
  { sensor: 'DS18B20',  type: 'Temperature',  protocol: '1-Wire',    range: '20 – 100 °C',    fault: 'Overheating, Insulation Degradation, Grease Loss', standard: 'IEC 60034-1' },
  { sensor: 'ACS712',   type: 'Current',      protocol: 'Analog',    range: '0 – 18.75 A',    fault: 'Overload, Phase Loss, Rotor Bar Fault', standard: 'IEC 60947-4-1' },
  { sensor: 'ADS1115',  type: 'ADC (16-bit)', protocol: 'I²C',       range: 'N/A',             fault: 'Signal Converter for ACS712', standard: '—' },
  { sensor: '16×2 LCD', type: 'Display',      protocol: 'I²C',       range: 'N/A',             fault: 'Local Status Output', standard: '—' },
  { sensor: 'Relay',    type: 'Switch',       protocol: 'GPIO',      range: 'N/A',             fault: 'Equipment Stop / Slowdown Actuator', standard: 'IEC 61810' },
]

const TECH_STACK = [
  { layer: 'Edge Compute',  tech: 'Raspberry Pi 4',         role: 'Central processing, GPIO control, sensor bus' },
  { layer: 'ML Engine',     tech: 'Python + scikit-learn',  role: 'KAIST-trained fault classifier, real-time inference' },
  { layer: 'Backend API',   tech: 'FastAPI + SQLite',       role: 'JWT auth, sensor endpoints, anomaly event log' },
  { layer: 'Frontend',      tech: 'React 19 + Recharts',    role: 'Real-time dashboards, alerts, 3D hardware explorer' },
  { layer: '3D Lab',        tech: '@react-three/fiber',     role: 'Interactive hardware assembly workbench' },
  { layer: 'Data Protocol', tech: 'WebSocket / MQTT',       role: 'Low-latency sensor streaming to dashboard' },
  { layer: 'Auth',          tech: 'JWT + Argon2',           role: 'Secure login, role-based access control' },
]

// ── Feedback / Ask Us section ──────────────────────────────────────────────
const FEEDBACK_STRINGS = {
  title:       { en: '💬 Ask Us / Send Feedback',        hi: '💬 हमसे पूछें / फ़ीडबैक भेजें',   kn: '💬 ನಮ್ಮನ್ನು ಕೇಳಿ / ಪ್ರತಿಕ್ರಿಯೆ ಕಳುಹಿಸಿ', ta: '💬 எங்களிடம் கேளுங்கள் / கருத்து அனுப்புங்கள்', te: '💬 మాకు అడగండి / అభిప్రాయం పంపండి' },
  subtitle:    { en: 'Have a question not covered above? Want to suggest a feature, report an issue, or just say hello? Write to us — we read every message.', hi: 'ऊपर नहीं दिया गया कोई सवाल है? Feature सुझाना चाहते हैं या कोई समस्या बताना? लिखें — हम हर संदेश पढ़ते हैं।', kn: 'ಮೇಲೆ ಉತ್ತರಿಸಲಾಗದ ಪ್ರಶ್ನೆ ಇದೆಯೇ? Feature ಸೂಚಿಸಲು ಅಥವಾ ಸಮಸ್ಯೆ ತಿಳಿಸಲು ಬರೆಯಿರಿ.', ta: 'மேலே விடையளிக்கப்படாத கேள்வி உள்ளதா? அம்சம் பரிந்துரைக்க அல்லது சிக்கல் தெரிவிக்க எழுதுங்கள்.', te: 'పైన సమాధానం ఇవ్వని ప్రశ్న ఉందా? ఫీచర్ సూచించాలా లేదా సమస్య నివేదించాలా? రాయండి.' },
  name_label:  { en: 'Your Name',       hi: 'आपका नाम',      kn: 'ನಿಮ್ಮ ಹೆಸರು',    ta: 'உங்கள் பெயர்',      te: 'మీ పేరు'         },
  email_label: { en: 'Email (optional)', hi: 'Email (वैकल्पिक)', kn: 'Email (ಐಚ್ಛಿಕ)', ta: 'மின்னஞ்சல் (விருப்பமான)', te: 'ఇమెయిల్ (ఐచ్ఛికం)' },
  type_label:  { en: 'Type',            hi: 'प्रकार',         kn: 'ಪ್ರಕಾರ',         ta: 'வகை',               te: 'రకం'              },
  msg_label:   { en: 'Your message',    hi: 'आपका संदेश',     kn: 'ನಿಮ್ಮ ಸಂದೇಶ',   ta: 'உங்கள் செய்தி',    te: 'మీ సందేశం'       },
  send_btn:    { en: '→ Send Message',  hi: '→ भेजें',        kn: '→ ಕಳುಹಿಸಿ',      ta: '→ அனுப்பு',        te: '→ పంపండి'        },
  success:     { en: '✅ Message received — thank you! We will review and respond soon.', hi: '✅ संदेश प्राप्त हुआ — धन्यवाद! हम जल्द समीक्षा करेंगे।', kn: '✅ ಸಂದೇಶ ಸ್ವೀಕರಿಸಲಾಗಿದೆ — ಧನ್ಯವಾದ!', ta: '✅ செய்தி பெறப்பட்டது — நன்றி!', te: '✅ సందేశం అందింది — ధన్యవాదాలు!' },
  err_empty:   { en: 'Please enter your name and message.', hi: 'नाम और संदेश दर्ज करें।', kn: 'ಹೆಸರು ಮತ್ತು ಸಂದೇಶ ನಮೂದಿಸಿ.', ta: 'பெயர் மற்றும் செய்தியை உள்ளிடவும்.', te: 'పేరు మరియు సందేశం నమోదు చేయండి.' },
  types: {
    en: ['General Question', 'Feature Request', 'Bug / Issue', 'Integration Help', 'Other'],
    hi: ['सामान्य प्रश्न', 'Feature अनुरोध', 'Bug / समस्या', 'एकीकरण सहायता', 'अन्य'],
    kn: ['ಸಾಮಾನ್ಯ ಪ್ರಶ್ನೆ', 'Feature ವಿನಂತಿ', 'Bug / ಸಮಸ್ಯೆ', 'ಏಕೀಕರಣ ಸಹಾಯ', 'ಇತರ'],
    ta: ['பொது கேள்வி', 'அம்சம் கோரிக்கை', 'பிழை / சிக்கல்', 'ஒருங்கிணைப்பு உதவி', 'மற்றவை'],
    te: ['సాధారణ ప్రశ్న', 'ఫీచర్ అభ్యర్థన', 'బగ్ / సమస్య', 'ఏకీకరణ సహాయం', 'ఇతర'],
  },
}

function FeedbackSection({ lang }) {
  const [name,    setName]    = useState('')
  const [email,   setEmail]   = useState('')
  const [type,    setType]    = useState('')
  const [msg,     setMsg]     = useState('')
  const [sent,    setSent]    = useState(false)
  const [err,     setErr]     = useState('')
  const [loading, setLoading] = useState(false)

  const fb = FEEDBACK_STRINGS
  const types = fb.types[lang] || fb.types.en

  function handleSubmit(e) {
    e.preventDefault()
    setErr('')
    if (!name.trim() || !msg.trim()) {
      setErr(fb.err_empty[lang] || fb.err_empty.en)
      return
    }
    setLoading(true)

    const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    fetch(`${API}/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: name.trim(),
        email: email.trim() || undefined,
        type: type || types[0],
        message: msg.trim(),
      }),
    })
      .then(r => {
        if (!r.ok) return r.json().then(d => Promise.reject(d?.detail || 'Server error'))
        return r.json()
      })
      .then(() => {
        setLoading(false)
        setSent(true)
      })
      .catch(errMsg => {
        setLoading(false)
        setErr(typeof errMsg === 'string' ? errMsg : (fb.err_empty[lang] || 'Submission failed. Please try again.'))
      })
  }

  if (sent) {
    return (
      <section className="about-section feedback-section">
        <div className="feedback-success">
          <span className="feedback-success-icon">✅</span>
          <p>{fb.success[lang] || fb.success.en}</p>
        </div>
      </section>
    )
  }

  return (
    <section className="about-section feedback-section">
      <h2 className="about-section-title">
        {fb.title[lang] || fb.title.en}
      </h2>
      <p className="about-section-intro">
        {fb.subtitle[lang] || fb.subtitle.en}
      </p>

      <form className="feedback-form" onSubmit={handleSubmit} noValidate>
        <div className="feedback-row">
          {/* Name */}
          <div className="feedback-field">
            <label className="feedback-label">{fb.name_label[lang] || fb.name_label.en}</label>
            <input
              className="feedback-input"
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder={fb.name_label[lang] || 'Your name'}
              disabled={loading}
            />
          </div>
          {/* Email */}
          <div className="feedback-field">
            <label className="feedback-label">{fb.email_label[lang] || fb.email_label.en}</label>
            <input
              className="feedback-input"
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="you@example.com"
              disabled={loading}
            />
          </div>
        </div>

        {/* Type */}
        <div className="feedback-field">
          <label className="feedback-label">{fb.type_label[lang] || fb.type_label.en}</label>
          <div className="feedback-type-chips">
            {types.map((tp, i) => (
              <button
                key={i}
                type="button"
                className={`feedback-type-chip${type === tp ? ' feedback-type-active' : ''}`}
                onClick={() => setType(tp)}
                disabled={loading}
              >
                {tp}
              </button>
            ))}
          </div>
        </div>

        {/* Message */}
        <div className="feedback-field">
          <label className="feedback-label">{fb.msg_label[lang] || fb.msg_label.en}</label>
          <textarea
            className="feedback-textarea"
            rows={5}
            value={msg}
            onChange={e => setMsg(e.target.value)}
            placeholder={lang === 'en' ? 'Write your question, suggestion, or feedback here…'
              : lang === 'hi' ? 'यहाँ अपना प्रश्न, सुझाव या फ़ीडबैक लिखें…'
              : lang === 'kn' ? 'ಇಲ್ಲಿ ನಿಮ್ಮ ಪ್ರಶ್ನೆ, ಸಲಹೆ ಅಥವಾ ಪ್ರತಿಕ್ರಿಯೆ ಬರೆಯಿರಿ…'
              : lang === 'ta' ? 'இங்கே உங்கள் கேள்வி, பரிந்துரை அல்லது கருத்தை எழுதுங்கள்…'
              : 'ఇక్కడ మీ ప్రశ్న, సూచన లేదా అభిప్రాయం రాయండి…'}
            disabled={loading}
          />
        </div>

        {err && (
          <div className="feedback-err">{err}</div>
        )}

        <button className="feedback-submit" type="submit" disabled={loading}>
          {loading
            ? <span className="login-spinner" />
            : (fb.send_btn[lang] || fb.send_btn.en)
          }
        </button>
      </form>
    </section>
  )
}

// ── FAQ accordion item ─────────────────────────────────────────────────────
function FAQItem({ item, index }) {  const [open, setOpen] = useState(false)
  return (
    <div className={`faq-item${open ? ' faq-open' : ''}`}>
      <button className="faq-q" onClick={() => setOpen(o => !o)}>
        <span className="faq-num">Q{index + 1}</span>
        <span className="faq-q-text">{item.q}</span>
        <span className="faq-chevron">{open ? '▲' : '▼'}</span>
      </button>
      {open && <div className="faq-a">{item.a}</div>}
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────
export default function AboutPage() {
  const lang = useLang()
  const faqs = FAQ[lang] || FAQ.en
  const objectives = OBJECTIVES[lang] || OBJECTIVES.en

  return (
    <main className="main about-page">

      {/* ── Hero ── */}
      <div className="about-hero">
        <div className="about-hero-eye">👁️</div>
        <div>
          <h1 className="about-hero-title">
            {CONTENT.hero_title[lang] || CONTENT.hero_title.en}
          </h1>
          <p className="about-hero-sub">
            {CONTENT.hero_sub[lang] || CONTENT.hero_sub.en}
          </p>
        </div>
      </div>

      {/* ── Objectives ── */}
      <section className="about-section">
        <h2 className="about-section-title">{CONTENT.sec_objective[lang] || CONTENT.sec_objective.en}</h2>
        <ul className="about-objectives">
          {objectives.map((obj, i) => (
            <li key={i} className="about-obj-item">
              <span className="about-obj-dot">✦</span>
              <span>{obj}</span>
            </li>
          ))}
        </ul>
      </section>

      {/* ── Protective Action System ── */}
      <section className="about-section">
        <h2 className="about-section-title">{CONTENT.sec_protection[lang] || CONTENT.sec_protection.en}</h2>
        <p className="about-section-intro">
          {lang === 'en' && 'IntelliWatch implements a three-tier protective response that mirrors industry-standard FMEA practices. Each tier is calibrated to preserve both hardware integrity and production continuity.'}
          {lang === 'hi' && 'IntelliWatch तीन-स्तरीय सुरक्षात्मक प्रतिक्रिया लागू करता है। प्रत्येक स्तर hardware सुरक्षा और उत्पादन निरंतरता दोनों को संतुलित करता है।'}
          {lang === 'kn' && 'IntelliWatch ಮೂರು-ಹಂತದ ರಕ್ಷಣಾ ಪ್ರತಿಕ್ರಿಯೆ ಅಳವಡಿಸಿದೆ. ಪ್ರತಿ ಹಂತ hardware ಸಂರಕ್ಷಣೆ ಮತ್ತು ಉತ್ಪಾದನಾ ನಿರಂತರತೆ ನಿರ್ವಹಿಸುತ್ತದೆ.'}
          {lang === 'ta' && 'IntelliWatch மூன்று அடுக்கு பாதுகாப்பு பதிலை செயல்படுத்துகிறது. ஒவ்வொரு அடுக்கும் வன்பொருள் பாதுகாப்பையும் உற்பத்தி தொடர்ச்சியையும் சமப்படுத்துகிறது.'}
          {lang === 'te' && 'IntelliWatch మూడు-స్థాయి రక్షణ ప్రతిస్పందనను అమలు చేస్తుంది. ప్రతి స్థాయి హార్డ్‌వేర్ భద్రత మరియు ఉత్పత్తి కొనసాగింపు రెండింటినీ సమతుల్యం చేస్తుంది.'}
        </p>

        <div className="protection-tiers">

          <div className="tier tier-normal">
            <div className="tier-icon">✅</div>
            <div className="tier-content">
              <h3 className="tier-title">
                {lang === 'en' && 'Normal — Steady Monitoring'}
                {lang === 'hi' && 'सामान्य — स्थिर निगरानी'}
                {lang === 'kn' && 'ಸಾಮಾನ್ಯ — ಸ್ಥಿರ ಮೇಲ್ವಿಚಾರಣೆ'}
                {lang === 'ta' && 'சாதாரண — நிலையான கண்காணிப்பு'}
                {lang === 'te' && 'సాధారణ — స్థిర మానిటరింగ్'}
              </h3>
              <p className="tier-desc">
                {lang === 'en' && 'Readings are within safe thresholds. IntelliWatch performs continuous background analysis — updating the ML model confidence score, logging readings to the database, and refreshing charts at a steady 3-second interval. No operator intervention is needed.'}
                {lang === 'hi' && 'रीडिंग सुरक्षित सीमा में हैं। IntelliWatch निरंतर background analysis करता है — ML confidence score update, database में readings log और 3-second interval पर charts refresh। कोई हस्तक्षेप जरूरी नहीं।'}
                {lang === 'kn' && 'Readings ಸುರಕ್ಷಿತ ಮಿತಿಯಲ್ಲಿದೆ. IntelliWatch ನಿರಂತರ background analysis ನಡೆಸುತ್ತದೆ — ML confidence update, database logging, 3-second chart refresh. ಯಾವ ಹಸ್ತಕ್ಷೇಪ ಅಗತ್ಯವಿಲ್ಲ.'}
                {lang === 'ta' && 'அளவீடுகள் பாதுகாப்பான வரம்பிற்குள் உள்ளன. IntelliWatch தொடர்ச்சியான background analysis செய்கிறது — ML confidence update, database logging, 3 நொடி chart refresh. எந்த தலையீடும் தேவையில்லை.'}
                {lang === 'te' && 'రీడింగ్‌లు సురక్షిత పరిధిలో ఉన్నాయి. IntelliWatch నిరంతర నేపథ్య విశ్లేషణ నిర్వహిస్తుంది — ML confidence update, database logging, 3-సెకన్ల చార్ట్ రిఫ్రెష్. ఎలాంటి జోక్యం అవసరం లేదు.'}
              </p>
            </div>
          </div>

          <div className="tier tier-warning">
            <div className="tier-icon">⚠️</div>
            <div className="tier-content">
              <h3 className="tier-title">
                {lang === 'en' && 'Warning — Graceful Speed Reduction'}
                {lang === 'hi' && 'चेतावनी — क्रमिक गति में कमी'}
                {lang === 'kn' && 'ಎಚ್ಚರಿಕೆ — ಕ್ರಮೇಣ ವೇಗ ಕಡಿತ'}
                {lang === 'ta' && 'எச்சரிக்கை — படிப்படியான வேக குறைப்பு'}
                {lang === 'te' && 'హెచ్చరిక — క్రమంగా వేగ తగ్గింపు'}
              </h3>
              <p className="tier-desc">
                {lang === 'en' && 'When readings enter the warning zone, IntelliWatch signals a controlled speed reduction. Motor RPM is reduced by 10–15% increments over 5–10 seconds, not cut instantly. This prevents bearing shock, eliminates surge currents, and gives the machine time to thermally stabilise. If the reading returns to normal within the window, the system resumes standard speed. If it continues rising, the critical stop is triggered.'}
                {lang === 'hi' && 'Warning zone में IntelliWatch controlled speed reduction signal करता है। Motor RPM 5–10 seconds में 10–15% steps में कम होता है। यह bearing shock, surge currents से बचाता है और machine को thermally stabilise होने का समय देता है। अगर readings normal हो जाएं तो standard speed resume होती है।'}
                {lang === 'kn' && 'Warning zone ನಲ್ಲಿ IntelliWatch controlled speed reduction signal ಮಾಡುತ್ತದೆ. Motor RPM 5–10 seconds ನಲ್ಲಿ 10–15% steps ನಲ್ಲಿ ಕಡಿಮೆ ಆಗುತ್ತದೆ. Readings normal ಆದರೆ standard speed resume ಆಗುತ್ತದೆ.'}
                {lang === 'ta' && 'Warning zone-ல் IntelliWatch controlled speed reduction சமிக்ஞை செய்கிறது. Motor RPM 5–10 நொடிகளில் 10–15% படிகளில் குறைகிறது. அளவீடுகள் சாதாரணமானால் standard வேகம் மீண்டும் தொடங்கும்.'}
                {lang === 'te' && 'Warning zone లో IntelliWatch controlled speed reduction సిగ్నల్ చేస్తుంది. Motor RPM 5–10 సెకన్లలో 10–15% స్టెప్‌లలో తగ్గుతుంది. రీడింగ్‌లు సాధారణమైతే standard వేగం మళ్ళీ ప్రారంభమవుతుంది.'}
              </p>
            </div>
          </div>

          <div className="tier tier-critical">
            <div className="tier-icon">🛑</div>
            <div className="tier-content">
              <h3 className="tier-title">
                {lang === 'en' && 'Critical — Immediate Equipment Stop'}
                {lang === 'hi' && 'गंभीर — तत्काल उपकरण रोक'}
                {lang === 'kn' && 'ಗಂಭೀರ — ತಕ್ಷಣ ಉಪಕರಣ ನಿಲ್ಲಿಸುವಿಕೆ'}
                {lang === 'ta' && 'நெருக்கடி — உடனடி உபகரண நிறுத்தம்'}
                {lang === 'te' && 'క్రిటికల్ — తక్షణ పరికరం ఆపు'}
              </h3>
              <p className="tier-desc">
                {lang === 'en' && 'When a sensor crosses the critical threshold, IntelliWatch issues an immediate hardware stop. The relay module on the Raspberry Pi GPIO opens the circuit, cutting motor power within milliseconds. This protects bearings, windings, and mechanical components from catastrophic failure. The dashboard enters a pulsing red alert state. All subsequent stop confirmations must be manually acknowledged by an authorized ADMIN or MAINTENANCE ENGINEER before the equipment can restart.'}
                {lang === 'hi' && 'Critical threshold पार होने पर IntelliWatch तत्काल hardware stop जारी करता है। Raspberry Pi GPIO relay circuit खोलता है, milliseconds में motor power cut। Dashboard pulsing red alert state में आता है। Restart के लिए authorized user की manual acknowledgment जरूरी है।'}
                {lang === 'kn' && 'Critical threshold ದಾಟಿದಾಗ Raspberry Pi GPIO relay circuit ತೆರೆಯುತ್ತದೆ, milliseconds ನಲ್ಲಿ motor power cut. Dashboard pulsing red state ನಲ್ಲಿ ಬರುತ್ತದೆ. Restart ಗೆ authorized user manual acknowledgment ಅಗತ್ಯ.'}
                {lang === 'ta' && 'Critical threshold மீறும்போது Raspberry Pi GPIO relay circuit திறக்கிறது, milliseconds-ல் motor power cut. Dashboard pulsing red alert state-க்கு வருகிறது. மறுதொடக்கத்திற்கு authorized user manual acknowledgment தேவை.'}
                {lang === 'te' && 'Critical threshold దాటినప్పుడు Raspberry Pi GPIO relay circuit తెరుచుకుంటుంది, milliseconds లో motor power cut. Dashboard pulsing red state కి వస్తుంది. Restart కి authorized user manual acknowledgment అవసరం.'}
              </p>
            </div>
          </div>

        </div>
      </section>

      {/* ── Sensors table ── */}
      <section className="about-section">
        <h2 className="about-section-title">{CONTENT.sec_sensors[lang] || CONTENT.sec_sensors.en}</h2>
        <div className="about-table-wrap">
          <table className="about-table">
            <thead>
              <tr>
                <th>Sensor</th>
                <th>Type</th>
                <th>Protocol</th>
                <th>Operating Range</th>
                <th>Fault Detection</th>
                <th>Standard</th>
              </tr>
            </thead>
            <tbody>
              {SENSOR_TABLE.map(row => (
                <tr key={row.sensor}>
                  <td className="about-td-sensor">{row.sensor}</td>
                  <td>{row.type}</td>
                  <td><span className="about-proto-chip">{row.protocol}</span></td>
                  <td>{row.range}</td>
                  <td>{row.fault}</td>
                  <td><span className="about-std-chip">{row.standard}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* ── Tech stack ── */}
      <section className="about-section">
        <h2 className="about-section-title">{CONTENT.sec_tech[lang] || CONTENT.sec_tech.en}</h2>
        <div className="tech-grid">
          {TECH_STACK.map(item => (
            <div key={item.layer} className="tech-card">
              <span className="tech-layer">{item.layer}</span>
              <span className="tech-name">{item.tech}</span>
              <span className="tech-role">{item.role}</span>
            </div>
          ))}
        </div>
      </section>

      {/* ── FAQ ── */}
      <section className="about-section">
        <h2 className="about-section-title">{CONTENT.sec_faq[lang] || CONTENT.sec_faq.en}</h2>
        <div className="faq-list">
          {faqs.map((item, i) => (
            <FAQItem key={i} item={item} index={i} />
          ))}
        </div>
      </section>

      {/* ── Feedback / Ask Us ── */}
      <FeedbackSection lang={lang} />

    </main>
  )
}
