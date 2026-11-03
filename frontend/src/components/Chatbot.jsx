
import { useState, useRef, useEffect, useCallback } from 'react'
import './Chatbot.css'

// ==================================================
// MULTI-LANGUAGE CHATBOT — IntelliWatch Assistant
// Features: text chat, multilingual, photo/doc
//           attachments, voice input (Web Speech API),
//           voice output (TTS), quick chips.
// ==================================================

const LANGUAGES = [
  { code: 'en', label: 'EN', name: 'English',  flag: '🇬🇧' },
  { code: 'hi', label: 'HI', name: 'हिन्दी',    flag: '🇮🇳' },
  { code: 'kn', label: 'KN', name: 'ಕನ್ನಡ',     flag: '🇮🇳' },
  { code: 'ta', label: 'TA', name: 'தமிழ்',     flag: '🇮🇳' },
  { code: 'te', label: 'TE', name: 'తెలుగు',    flag: '🇮🇳' },
]

// Speech-recognition locale codes
const LANG_LOCALE = { en: 'en-IN', hi: 'hi-IN', kn: 'kn-IN', ta: 'ta-IN', te: 'te-IN' }

// ==================================================
// MULTILINGUAL KNOWLEDGE BASE
// ==================================================

const KB = {
  en: {
    greeting: "Hello! I'm Bolt ⚡ — your IntelliWatch assistant. I can answer questions about vibration, temperature, current monitoring, anomaly detection, and system health. How can I help?",
    fallback: "I'm not sure about that specific question. I specialise in IntelliWatch topics like sensor monitoring, anomaly detection, thresholds, and maintenance recommendations. Could you rephrase?",
    about: "IntelliWatch is a real-time anomaly detection and decision support system. It monitors vibration, temperature, and current sensors from industrial machinery and uses machine learning to identify faults early.",
    vibration: "The vibration sensor (ADXL345) measures RMS velocity in mm/s (ISO 10816-3, Group 2, rigid mount). Normal: ≤ 4.5 mm/s. Warning: 4.5–7.1 mm/s (Unsatisfactory). Critical: > 7.1 mm/s (Unacceptable — stop equipment). Anomalies indicate bearing faults (BPFI/BPFO), misalignment, or rotor unbalance.",
    temperature: "The temperature sensor (DS18B20) uses 1-Wire protocol. Per IEC 60034-1 Class F insulation (40 °C ambient): Normal 20–80 °C. Warning 80–100 °C (elevated — inspect lubrication). Critical > 100 °C (risk of insulation breakdown — stop immediately).",
    current: "The current sensor (ACS712) uses the Hall effect. Per IEC 60947-4-1 for a 7.5 kW / 415 V motor (rated 15 A): Normal ≤ 16.5 A (110 % rated). Warning 16.5–18.75 A (110–125 %). Critical > 18.75 A (thermal overload relay trip threshold).",
    iot: "IntelliWatch uses a Raspberry Pi as the central processing unit. Sensors connect via GPIO, I²C, SPI, and 1-Wire protocols. Data is pushed to the dashboard over WebSocket or MQTT in real time.",
    alert: "Alerts are generated when sensor readings cross warning or critical thresholds. The Alert Log on every page records each event with a timestamp, severity, and the sensor that triggered it.",
    roles: "IntelliWatch supports three roles: ADMIN (full access, can manage users), OPERATOR (can view dashboards), and MAINTENANCE ENGINEER (can view data and run diagnostics).",
    ml: "IntelliWatch uses KAIST bearing fault dataset features to train classifiers that detect BPFI, BPFO, misalignment, and unbalance faults. The model runs on the Raspberry Pi via the IntelliWatch Brain engine.",
    status: "System status is derived from all sensor states. It shows Normal (green), Warning (amber), Critical (red with pulsing animation), or Awaiting IoT Signal (grey) when no data is connected yet.",
    explorer: "The 3D Explorer lets you virtually assemble the IntelliWatch hardware on a workbench. You can place, move, rotate, and remove components with full undo/redo support.",
    leaderboard: "The TenderWatch Leaderboard shows which organisations are leading in adopting IntelliWatch-style predictive maintenance systems. Rankings are based on monitored assets, uptime scores, and anomaly response time.",
    attachment_ack: "Thanks for sharing that! I can see you've attached a file. As an on-device assistant I can't process file contents directly, but if you describe what you see or ask a specific question about it, I'll do my best to help.",
    voice_ack: "I heard you! Processing your voice message now…",
  },
  hi: {
    greeting: "नमस्ते! मैं Bolt ⚡ हूँ — आपका IntelliWatch सहायक। मैं कंपन, तापमान, करंट मॉनिटरिंग और anomaly detection के बारे में सवालों के जवाब दे सकता हूँ। बताइए कैसे मदद करूँ?",
    fallback: "इस सवाल का सटीक जवाब मुझे नहीं पता। IntelliWatch के sensor monitoring और maintenance से जुड़े सवाल दोबारा पूछ सकते हैं?",
    about: "IntelliWatch एक real-time anomaly detection और decision support system है।",
    vibration: "कंपन sensor (ADXL345) ISO 10816-3: सामान्य ≤ 4.5 mm/s, चेतावनी 4.5–7.1 mm/s, critical > 7.1 mm/s।",
    temperature: "तापमान sensor (DS18B20) IEC 60034-1 Class F: सामान्य 20–80°C, चेतावनी 80–100°C, critical > 100°C।",
    current: "करंट sensor (ACS712) IEC 60947-4-1: सामान्य ≤ 16.5 A, चेतावनी 16.5–18.75 A, critical > 18.75 A।",
    iot: "Raspberry Pi मुख्य processing unit है। Data WebSocket या MQTT से dashboard तक पहुँचता है।",
    alert: "Alert Log हर event को समय, गंभीरता और sensor के साथ record करता है।",
    roles: "ADMIN (पूर्ण access), OPERATOR (dashboard), MAINTENANCE ENGINEER (diagnostics)।",
    ml: "KAIST dataset से BPFI, BPFO, misalignment और unbalance detect होती है।",
    status: "Normal (हरा), Warning (पीला), Critical (लाल), Awaiting IoT (ग्रे)।",
    explorer: "3D Explorer में hardware virtual workbench पर assemble कर सकते हैं।",
    leaderboard: "TenderWatch Leaderboard दिखाता है कि कौन से organizations आगे हैं।",
    attachment_ack: "फ़ाइल शेयर करने के लिए धन्यवाद! मैं फ़ाइल की content सीधे process नहीं कर सकता, लेकिन अगर आप describe करें तो मैं help कर सकता हूँ।",
    voice_ack: "आपकी आवाज़ सुन ली! अभी process कर रहा हूँ…",
  },
  kn: {
    greeting: "ನಮಸ್ಕಾರ! ನಾನು Bolt ⚡ — ನಿಮ್ಮ IntelliWatch ಸಹಾಯಕ. ಕಂಪನ, ತಾಪಮಾನ, ಮತ್ತು anomaly detection ಬಗ್ಗೆ ಸಹಾಯ ಮಾಡಬಲ್ಲೆ.",
    fallback: "ಆ ಪ್ರಶ್ನೆಗೆ ನನಗೆ ಖಚಿತ ಉತ್ತರ ತಿಳಿದಿಲ್ಲ. ಮರು ಕೇಳಬಹುದೇ?",
    about: "IntelliWatch ಒಂದು real-time anomaly detection ಮತ್ತು decision support system.",
    vibration: "ADXL345 ISO 10816-3: ಸಾಮಾನ್ಯ ≤ 4.5 mm/s, ಎಚ್ಚರಿಕೆ 4.5–7.1 mm/s, critical > 7.1 mm/s.",
    temperature: "DS18B20 IEC 60034-1 Class F: ಸಾಮಾನ್ಯ 20–80°C, ಎಚ್ಚರಿಕೆ 80–100°C, critical > 100°C.",
    current: "ACS712 IEC 60947-4-1: ಸಾಮಾನ್ಯ ≤ 16.5 A, ಎಚ್ಚರಿಕೆ 16.5–18.75 A, critical > 18.75 A.",
    iot: "Raspberry Pi ಮೂಲಕ sensors GPIO, I²C ಮೂಲಕ ಸಂಪರ್ಕ.",
    alert: "Alert Log ಪ್ರತಿ event ಅನ್ನು timestamp ಮತ್ತು severity ಸಹಿತ ದಾಖಲಿಸುತ್ತದೆ.",
    roles: "ADMIN, OPERATOR, MAINTENANCE ENGINEER.",
    ml: "KAIST dataset: BPFI, BPFO, misalignment, unbalance.",
    status: "Normal (ಹಸಿರು), Warning (ಹಳದಿ), Critical (ಕೆಂಪು), Awaiting IoT (ಬೂದು).",
    explorer: "3D Explorer ನಲ್ಲಿ hardware virtual workbench ಮೇಲೆ assemble ಮಾಡಬಹುದು.",
    leaderboard: "TenderWatch Leaderboard ಯಾವ organizations ಮುಂದಿದ್ದಾರೆ ಎಂದು ತೋರಿಸುತ್ತದೆ.",
    attachment_ack: "ಫೈಲ್ ಶೇರ್ ಮಾಡಿದ್ದಕ್ಕೆ ಧನ್ಯವಾದ! ನೇರವಾಗಿ process ಮಾಡಲಾಗದು, ಆದರೆ describe ಮಾಡಿದರೆ ಸಹಾಯ ಮಾಡಬಲ್ಲೆ.",
    voice_ack: "ಧ್ವನಿ ಸ್ವೀಕರಿಸಲಾಗಿದೆ! Process ಮಾಡಲಾಗುತ್ತಿದೆ…",
  },
  ta: {
    greeting: "வணக்கம்! நான் Bolt ⚡ — உங்கள் IntelliWatch உதவியாளர். அதிர்வு, வெப்பநிலை மற்றும் anomaly detection பற்றி சேவை செய்வேன்.",
    fallback: "இந்த கேள்விக்கு எனக்கு சரியான பதில் தெரியவில்லை. மீண்டும் கேளுங்கள்.",
    about: "IntelliWatch ஒரு real-time anomaly detection மற்றும் decision support system.",
    vibration: "ADXL345 ISO 10816-3: சாதாரண ≤ 4.5 mm/s, எச்சரிக்கை 4.5–7.1 mm/s, critical > 7.1 mm/s.",
    temperature: "DS18B20 IEC 60034-1 Class F: சாதாரண 20–80°C, எச்சரிக்கை 80–100°C, critical > 100°C.",
    current: "ACS712 IEC 60947-4-1: சாதாரண ≤ 16.5 A, எச்சரிக்கை 16.5–18.75 A, critical > 18.75 A.",
    iot: "Raspberry Pi GPIO, I²C மூலம் sensors இணைக்கப்படுகின்றன.",
    alert: "Alert Log ஒவ்வொரு நிகழ்வையும் timestamp உடன் பதிவு செய்கிறது.",
    roles: "ADMIN, OPERATOR, MAINTENANCE ENGINEER.",
    ml: "KAIST dataset: BPFI, BPFO, misalignment, unbalance.",
    status: "Normal (பச்சை), Warning (மஞ்சள்), Critical (சிவப்பு), Awaiting IoT (சாம்பல்).",
    explorer: "3D Explorer இல் hardware virtual workbench மேல் assemble செய்யலாம்.",
    leaderboard: "TenderWatch Leaderboard எந்த organizations முன்னிலையில் உள்ளன என்பதை காட்டுகிறது.",
    attachment_ack: "கோப்பு பகிர்ந்தமைக்கு நன்றி! நேரடியாக process செய்ய இயலாது, ஆனால் describe செய்தால் உதவுவேன்.",
    voice_ack: "குரல் கேட்டேன்! இப்போது process செய்கிறேன்…",
  },
  te: {
    greeting: "నమస్కారం! నేను Bolt ⚡ — మీ IntelliWatch సహాయకుడు. కంపనం, ఉష్ణోగ్రత మరియు anomaly detection గురించి సహాయం చేయగలను.",
    fallback: "ఆ ప్రశ్నకు నాకు సరైన సమాధానం తెలియదు. మళ్ళీ అడగగలరా?",
    about: "IntelliWatch అనేది real-time anomaly detection మరియు decision support system.",
    vibration: "ADXL345 ISO 10816-3: సాధారణ ≤ 4.5 mm/s, హెచ్చరిక 4.5–7.1 mm/s, critical > 7.1 mm/s.",
    temperature: "DS18B20 IEC 60034-1 Class F: సాధారణ 20–80°C, హెచ్చరిక 80–100°C, critical > 100°C.",
    current: "ACS712 IEC 60947-4-1: సాధారణ ≤ 16.5 A, హెచ్చరిక 16.5–18.75 A, critical > 18.75 A.",
    iot: "Raspberry Pi GPIO, I²C ద్వారా sensors అనుసంధానం.",
    alert: "Alert Log ప్రతి సంఘటనను timestamp తో నమోదు చేస్తుంది.",
    roles: "ADMIN, OPERATOR, MAINTENANCE ENGINEER.",
    ml: "KAIST dataset: BPFI, BPFO, misalignment, unbalance.",
    status: "Normal (ఆకుపచ్చ), Warning (పసుపు), Critical (ఎరుపు), Awaiting IoT (బూడిద).",
    explorer: "3D Explorer లో hardware virtual workbench పై assemble చేయవచ్చు.",
    leaderboard: "TenderWatch Leaderboard ఏ organizations ముందున్నాయో చూపిస్తుంది.",
    attachment_ack: "ఫైల్ పంచుకున్నందుకు ధన్యవాదాలు! నేరుగా process చేయలేను, కానీ describe చేస్తే సహాయం చేస్తాను.",
    voice_ack: "మీ స్వరం విన్నాను! ఇప్పుడు process చేస్తున్నాను…",
  },
}

// ==================================================
// KEYWORD MATCHING ENGINE
// ==================================================

function classifyMessage(text) {
  const t = text.toLowerCase()
  if (/\b(hi|hello|hey|namaste|vanakkam|namaskara|namaskar|help|start)\b/.test(t)) return 'greeting'
  if (/\b(what|about|intelliwatch|system|project|overview|explain)\b/.test(t)) return 'about'
  if (/\b(vibrat|adxl|shake|oscillat|कंपन|ಕಂಪನ|అదురు|அதிர்)\b/.test(t)) return 'vibration'
  if (/\b(temp|heat|ds18|thermal|celsius|degree|तापमान|ಉಷ್ಣ|வெப்ப|ఉష్ణ)\b/.test(t)) return 'temperature'
  if (/\b(current|amp|acs|motor|power|करंट|ಮಿನ್ನ|மின்|విద్యుత్)\b/.test(t)) return 'current'
  if (/\b(iot|raspberry|sensor|hardware|connect|wire|gpio|i2c|mqtt|websocket)\b/.test(t)) return 'iot'
  if (/\b(alert|log|notif|alarm|warn|critical|threshold|event)\b/.test(t)) return 'alert'
  if (/\b(role|admin|operator|engineer|user|access|login|auth|permission)\b/.test(t)) return 'roles'
  if (/\b(ml|machine|learn|model|kaist|fault|bpfi|bpfo|misalign|unbalanc|predict|classif)\b/.test(t)) return 'ml'
  if (/\b(status|health|system|online|offline|live|state)\b/.test(t)) return 'status'
  if (/\b(3d|explorer|hardware|lab|workbench|place|component|drag)\b/.test(t)) return 'explorer'
  if (/\b(leader|board|rank|tender|top|org|company|chart)\b/.test(t)) return 'leaderboard'
  return 'fallback'
}

// File type helpers
function isImage(file) { return file.type.startsWith('image/') }
function fileIcon(file) {
  if (isImage(file)) return '🖼️'
  if (file.type === 'application/pdf') return '📄'
  if (file.name.match(/\.(doc|docx)$/i)) return '📝'
  if (file.name.match(/\.(xls|xlsx)$/i)) return '📊'
  if (file.name.match(/\.(txt|csv|md)$/i)) return '📃'
  return '📎'
}

// ==================================================
// ROBOT AVATAR SVG
// ==================================================

function RobotAvatar({ size = 56, glow = true, pulse = false }) {
  return (
    <svg
      width={size} height={size} viewBox="0 0 100 100"
      fill="none" xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      className={`robot-avatar${glow ? ' robot-glow' : ''}${pulse ? ' robot-pulse' : ''}`}
    >
      <defs>
        <radialGradient id="bgGrad" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#1e40af" />
          <stop offset="100%" stopColor="#0a0f2e" />
        </radialGradient>
        <radialGradient id="bodyW" cx="38%" cy="30%" r="62%">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="100%" stopColor="#c8d6e8" />
        </radialGradient>
        <radialGradient id="visor" cx="50%" cy="55%" r="55%">
          <stop offset="0%" stopColor="#1e2030" />
          <stop offset="100%" stopColor="#0a0c18" />
        </radialGradient>
        <radialGradient id="eyeL" cx="40%" cy="35%" r="60%">
          <stop offset="0%" stopColor="#a5f3fc" />
          <stop offset="100%" stopColor="#0891b2" />
        </radialGradient>
        <radialGradient id="eyeR" cx="40%" cy="35%" r="60%">
          <stop offset="0%" stopColor="#a5f3fc" />
          <stop offset="100%" stopColor="#0891b2" />
        </radialGradient>
        <radialGradient id="orbG" cx="40%" cy="35%" r="60%">
          <stop offset="0%" stopColor="#67e8f9" />
          <stop offset="100%" stopColor="#0e7490" />
        </radialGradient>
        <filter id="glow" x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="1.8" result="g" />
          <feMerge><feMergeNode in="g"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
        <filter id="softShadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="2" stdDeviation="2" floodColor="#000" floodOpacity="0.25"/>
        </filter>
      </defs>
      <circle cx="50" cy="50" r="49" fill="url(#bgGrad)" />
      <circle cx="50" cy="50" r="47" fill="none" stroke="#3b82f6" strokeWidth="1.5" strokeOpacity="0.7" />
      <rect x="31" y="62" width="38" height="26" rx="10" fill="url(#bodyW)" filter="url(#softShadow)" />
      <circle cx="29" cy="66" r="5.5" fill="#d1dde8" stroke="#b0c0d0" strokeWidth="0.8" />
      <circle cx="71" cy="66" r="5.5" fill="#d1dde8" stroke="#b0c0d0" strokeWidth="0.8" />
      <rect x="40" y="68" width="20" height="16" rx="5" fill="#1e293b" />
      <circle cx="50" cy="76" r="5.5" fill="url(#orbG)" filter="url(#glow)" />
      <circle cx="50" cy="76" r="3" fill="#cffafe" fillOpacity="0.6" />
      <g transform="translate(12, 60) rotate(-15)">
        <rect x="0" y="0" width="11" height="16" rx="5" fill="url(#bodyW)" />
        <rect x="-1" y="14" width="13" height="12" rx="5" fill="url(#bodyW)" />
        <rect x="4" y="5" width="6" height="12" rx="3" fill="url(#bodyW)" />
      </g>
      <g transform="translate(65, 42)">
        <rect x="0" y="0" width="20" height="13" rx="5" fill="white" fillOpacity="0.92" />
        <polygon points="4,13 0,18 9,13" fill="white" fillOpacity="0.92" />
        <circle cx="5" cy="6.5" r="1.8" fill="#3b82f6" />
        <circle cx="10" cy="6.5" r="1.8" fill="#3b82f6" />
        <circle cx="15" cy="6.5" r="1.8" fill="#3b82f6" />
      </g>
      <rect x="24" y="18" width="52" height="46" rx="16" fill="url(#bodyW)" filter="url(#softShadow)" />
      <ellipse cx="38" cy="24" rx="8" ry="4" fill="white" fillOpacity="0.35" />
      <rect x="47" y="9" width="6" height="11" rx="3" fill="#d1dde8" />
      <rect x="43" y="6" width="14" height="5" rx="2.5" fill="#1e293b" />
      <rect x="46" y="7" width="8" height="2" rx="1" fill="#38bdf8" filter="url(#glow)" />
      <rect x="29" y="26" width="42" height="30" rx="12" fill="url(#visor)" />
      <ellipse cx="40" cy="31" rx="7" ry="3" fill="white" fillOpacity="0.1" />
      <path d="M 35 42 Q 39 36 43 42" stroke="url(#eyeL)" strokeWidth="2.5" fill="none" strokeLinecap="round" filter="url(#glow)" />
      <path d="M 47 42 Q 51 36 55 42" stroke="url(#eyeR)" strokeWidth="2.5" fill="none" strokeLinecap="round" filter="url(#glow)" />
      <circle cx="43" cy="40" r="1.2" fill="#a5f3fc" fillOpacity="0.9" />
      <circle cx="55" cy="40" r="1.2" fill="#a5f3fc" fillOpacity="0.9" />
      <ellipse cx="34" cy="46" rx="4.5" ry="2.5" fill="#f472b6" fillOpacity="0.35" />
      <ellipse cx="56" cy="46" rx="4.5" ry="2.5" fill="#f472b6" fillOpacity="0.35" />
      <path d="M 38 50 Q 45 56 57 50" stroke="#f9a8d4" strokeWidth="1.8" fill="none" strokeLinecap="round" />
      <path d="M 24 35 Q 50 8 76 35" stroke="#1e293b" strokeWidth="4" fill="none" strokeLinecap="round" />
      <rect x="18" y="32" width="12" height="16" rx="6" fill="#1e293b" />
      <rect x="20" y="34" width="8" height="12" rx="4" fill="#0f172a" />
      <circle cx="24" cy="40" r="4.5" fill="none" stroke="#38bdf8" strokeWidth="1.2" />
      <circle cx="24" cy="40" r="2" fill="#0891b2" fillOpacity="0.6" />
      <rect x="70" y="32" width="12" height="16" rx="6" fill="#1e293b" />
      <rect x="72" y="34" width="8" height="12" rx="4" fill="#0f172a" />
      <circle cx="76" cy="40" r="4.5" fill="none" stroke="#38bdf8" strokeWidth="1.2" />
      <circle cx="76" cy="40" r="2" fill="#0891b2" fillOpacity="0.6" />
      <path d="M 22 48 Q 28 58 38 60" stroke="#374151" strokeWidth="2" fill="none" strokeLinecap="round" />
      <rect x="35" y="57" width="9" height="6" rx="3" fill="#1e293b" />
      <rect x="36.5" y="58" width="6" height="4" rx="2" fill="#0891b2" fillOpacity="0.7" />
      <circle cx="40" cy="60" r="1.2" fill="#38bdf8" filter="url(#glow)" />
    </svg>
  )
}

// ==================================================
// ATTACHMENT PREVIEW — shown inside a chat bubble
// ==================================================

function AttachmentPreview({ file, dataUrl }) {
  if (isImage(file) && dataUrl) {
    return (
      <div className="attach-preview">
        <img src={dataUrl} alt={file.name} className="attach-img" />
        <span className="attach-name">{file.name}</span>
      </div>
    )
  }
  return (
    <div className="attach-file">
      <span className="attach-file-icon">{fileIcon(file)}</span>
      <div className="attach-file-info">
        <span className="attach-file-name">{file.name}</span>
        <span className="attach-file-size">{(file.size / 1024).toFixed(1)} KB</span>
      </div>
    </div>
  )
}

// ==================================================
// MAIN CHATBOT COMPONENT
// ==================================================

export default function Chatbot() {
  const [open, setOpen]             = useState(false)
  const [lang, setLang]             = useState('en')
  const [input, setInput]           = useState('')
  const [messages, setMessages]     = useState([])
  const [typing, setTyping]         = useState(false)
  const [showLang, setShowLang]     = useState(false)

  // Attachment state
  const [pendingFiles, setPendingFiles] = useState([])   // { file, dataUrl }[]
  const fileInputRef  = useRef(null)

  // Voice-input state
  const [listening, setListening]   = useState(false)
  const [voiceError, setVoiceError] = useState('')
  const [interimText, setInterimText] = useState('')
  const recognitionRef = useRef(null)

  // Voice-output (TTS) state
  const [ttsEnabled, setTtsEnabled] = useState(false)

  const messagesEndRef = useRef(null)
  const inputRef       = useRef(null)

  // ── Init greeting ────────────────────────────────────────────────────────
  useEffect(() => {
    if (open && messages.length === 0) addBotMessage(KB[lang].greeting)
    if (open) setTimeout(() => inputRef.current?.focus(), 120)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  // ── Auto-scroll ──────────────────────────────────────────────────────────
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, typing])

  // ── Close lang dropdown on outside click ─────────────────────────────────
  useEffect(() => {
    if (!showLang) return
    const close = () => setShowLang(false)
    window.addEventListener('mousedown', close)
    return () => window.removeEventListener('mousedown', close)
  }, [showLang])

  // ── Stop recognition on panel close ──────────────────────────────────────
  useEffect(() => {
    if (!open && recognitionRef.current) {
      recognitionRef.current.abort()
      setListening(false)
      setInterimText('')
    }
  }, [open])

  // ── TTS speak helper ─────────────────────────────────────────────────────
  const speak = useCallback((text) => {
    if (!ttsEnabled || !window.speechSynthesis) return
    window.speechSynthesis.cancel()
    const utt = new SpeechSynthesisUtterance(text)
    utt.lang = LANG_LOCALE[lang] || 'en-IN'
    utt.rate = 1.05
    window.speechSynthesis.speak(utt)
  }, [ttsEnabled, lang])

  function addBotMessage(text) {
    const msg = { id: Date.now() + Math.random(), role: 'bot', text }
    setMessages(prev => [...prev, msg])
    speak(text)
  }

  // ── Send message (text + optional attachments) ───────────────────────────
  function sendMessage(overrideText) {
    const text = (overrideText ?? input).trim()
    const hasFiles = pendingFiles.length > 0

    if (!text && !hasFiles) return

    // Build user message
    const userMsg = {
      id: Date.now(),
      role: 'user',
      text: text || null,
      files: hasFiles ? [...pendingFiles] : null,
    }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setPendingFiles([])
    setTyping(true)

    let response
    if (hasFiles && !text) {
      response = KB[lang].attachment_ack || KB.en.attachment_ack
    } else {
      const topic = classifyMessage(text)
      response = KB[lang][topic] || KB[lang].fallback
    }

    setTimeout(() => {
      setTyping(false)
      addBotMessage(response)
    }, 900 + Math.random() * 400)
  }

  function handleKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  // ── Language change ───────────────────────────────────────────────────────
  function handleLangChange(code) {
    setLang(code)
    setMessages([])
    setShowLang(false)
    setTyping(false)
    if (recognitionRef.current) { recognitionRef.current.abort(); setListening(false) }
    setTimeout(() => addBotMessage(KB[code].greeting), 200)
  }

  // ── File attachment ───────────────────────────────────────────────────────
  function handleFileChange(e) {
    const files = Array.from(e.target.files || [])
    if (!files.length) return
    files.forEach(file => {
      if (isImage(file)) {
        const reader = new FileReader()
        reader.onload = (ev) => {
          setPendingFiles(prev => [...prev, { file, dataUrl: ev.target.result }])
        }
        reader.readAsDataURL(file)
      } else {
        setPendingFiles(prev => [...prev, { file, dataUrl: null }])
      }
    })
    e.target.value = ''
  }

  function removePendingFile(idx) {
    setPendingFiles(prev => prev.filter((_, i) => i !== idx))
  }

  // ── Voice input (Web Speech API) ─────────────────────────────────────────
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
  const hasSpeech = !!SpeechRecognition

  function toggleVoice() {
    setVoiceError('')
    if (listening) {
      recognitionRef.current?.stop()
      setListening(false)
      setInterimText('')
      return
    }

    if (!hasSpeech) {
      setVoiceError('Voice input not supported in this browser.')
      return
    }

    const rec = new SpeechRecognition()
    rec.lang          = LANG_LOCALE[lang] || 'en-IN'
    rec.interimResults = true
    rec.continuous    = false
    rec.maxAlternatives = 1

    rec.onstart  = () => { setListening(true); setInterimText('') }
    rec.onend    = () => { setListening(false); setInterimText('') }
    rec.onerror  = (ev) => {
      setListening(false)
      setInterimText('')
      if (ev.error !== 'aborted') setVoiceError(`Mic error: ${ev.error}`)
    }
    rec.onresult = (ev) => {
      let final = '', interim = ''
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        const t = ev.results[i][0].transcript
        if (ev.results[i].isFinal) final += t
        else interim += t
      }
      if (interim) setInterimText(interim)
      if (final.trim()) {
        setInterimText('')
        setInput(prev => (prev ? prev + ' ' : '') + final.trim())
        rec.stop()
      }
    }

    recognitionRef.current = rec
    rec.start()
  }

  // ── TTS toggle ────────────────────────────────────────────────────────────
  function toggleTts() {
    if (ttsEnabled && window.speechSynthesis) window.speechSynthesis.cancel()
    setTtsEnabled(v => !v)
  }

  const currentLang = LANGUAGES.find(l => l.code === lang)

  const PLACEHOLDERS = {
    en: 'Ask about IntelliWatch…',
    hi: 'IntelliWatch के बारे में पूछें…',
    kn: 'IntelliWatch ಬಗ್ಗೆ ಕೇಳಿ…',
    ta: 'IntelliWatch பற்றி கேளுங்கள்…',
    te: 'IntelliWatch గురించి అడగండి…',
  }

  return (
    <>
      {/* ── Floating trigger button ── */}
      <button
        className={`chatbot-fab ${open ? 'chatbot-fab-open' : ''}`}
        onClick={() => setOpen(o => !o)}
        aria-label="Open IntelliWatch Assistant"
        title="Chat with Bolt — IntelliWatch AI"
      >
        <RobotAvatar size={46} glow pulse={!open} />
        {!open && <span className="chatbot-fab-badge">AI</span>}
      </button>

      {/* ── Chat panel ── */}
      {open && (
        <div className="chatbot-panel" role="dialog" aria-label="IntelliWatch Chatbot">

          {/* Header */}
          <div className="chatbot-header">
            <div className="chatbot-header-left">
              <RobotAvatar size={36} glow />
              <div>
                <span className="chatbot-name">Bolt</span>
                <span className="chatbot-tagline">IntelliWatch Assistant</span>
              </div>
            </div>

            <div className="chatbot-header-right">
              {/* TTS toggle */}
              <button
                className={`chatbot-icon-btn${ttsEnabled ? ' chatbot-icon-btn--active' : ''}`}
                onClick={toggleTts}
                title={ttsEnabled ? 'Mute voice responses' : 'Enable voice responses'}
                aria-label={ttsEnabled ? 'Mute' : 'Unmute'}
              >
                {ttsEnabled ? '🔊' : '🔇'}
              </button>

              {/* Language selector */}
              <div className="lang-selector-wrap" onMouseDown={e => e.stopPropagation()}>
                <button
                  className="lang-btn"
                  onClick={() => setShowLang(s => !s)}
                  title="Change language"
                  aria-label="Select language"
                >
                  {currentLang.flag} {currentLang.label}
                  <span className="lang-chevron">{showLang ? '▲' : '▼'}</span>
                </button>

                {showLang && (
                  <div className="lang-dropdown">
                    {LANGUAGES.map(l => (
                      <button
                        key={l.code}
                        className={`lang-option ${l.code === lang ? 'lang-active' : ''}`}
                        onClick={() => handleLangChange(l.code)}
                      >
                        <span>{l.flag}</span>
                        <span className="lang-opt-code">{l.label}</span>
                        <span className="lang-opt-name">{l.name}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <button
                className="chatbot-close"
                onClick={() => setOpen(false)}
                aria-label="Close chat"
              >✕</button>
            </div>
          </div>

          {/* Messages */}
          <div className="chatbot-messages">
            {messages.map(msg => (
              <div key={msg.id} className={`chat-msg chat-msg-${msg.role}`}>
                {msg.role === 'bot' && (
                  <span className="chat-avatar">
                    <RobotAvatar size={24} glow={false} />
                  </span>
                )}
                <div className="chat-bubble">
                  {/* Text content */}
                  {msg.text && <span>{msg.text}</span>}
                  {/* Attached files */}
                  {msg.files && msg.files.length > 0 && (
                    <div className={`chat-attachments${msg.text ? ' chat-attachments--below' : ''}`}>
                      {msg.files.map((f, i) => (
                        <AttachmentPreview key={i} file={f.file} dataUrl={f.dataUrl} />
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {typing && (
              <div className="chat-msg chat-msg-bot">
                <span className="chat-avatar">
                  <RobotAvatar size={24} glow={false} />
                </span>
                <div className="chat-bubble chat-typing">
                  <span /><span /><span />
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Quick chips */}
          <div className="chatbot-chips">
            {[
              { label: '📡 Vibration',    key: 'vibration'   },
              { label: '🌡️ Temperature',  key: 'temperature' },
              { label: '⚡ Current',      key: 'current'     },
              { label: '🔔 Alerts',       key: 'alert'       },
            ].map(chip => (
              <button
                key={chip.key}
                className="chip"
                onClick={() => {
                  const response = KB[lang][chip.key]
                  const botMsg = { id: Date.now() + 1, role: 'bot', text: response }
                  setMessages(prev => [
                    ...prev,
                    { id: Date.now(), role: 'user', text: chip.label, files: null },
                    botMsg,
                  ])
                  speak(response)
                }}
              >
                {chip.label}
              </button>
            ))}
          </div>

          {/* Pending file previews */}
          {pendingFiles.length > 0 && (
            <div className="chatbot-pending-files">
              {pendingFiles.map((f, i) => (
                <div key={i} className="pending-file-chip">
                  <span className="pending-file-icon">{fileIcon(f.file)}</span>
                  <span className="pending-file-name">{f.file.name}</span>
                  <button
                    className="pending-file-remove"
                    onClick={() => removePendingFile(i)}
                    aria-label="Remove attachment"
                  >×</button>
                </div>
              ))}
            </div>
          )}

          {/* Voice interim transcript */}
          {(listening || interimText) && (
            <div className="chatbot-voice-bar">
              <span className="voice-ripple" />
              <span className="voice-interim">
                {interimText || 'Listening…'}
              </span>
            </div>
          )}

          {/* Voice error */}
          {voiceError && (
            <div className="chatbot-voice-error">
              ⚠ {voiceError}
              <button onClick={() => setVoiceError('')} aria-label="Dismiss">×</button>
            </div>
          )}

          {/* Input row */}
          <div className="chatbot-input-row">
            {/* Attachment button */}
            <button
              className="chatbot-icon-btn chatbot-attach-btn"
              onClick={() => fileInputRef.current?.click()}
              title="Attach photo or document"
              aria-label="Attach file"
            >
              📎
            </button>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept="image/*,.pdf,.doc,.docx,.txt,.csv,.md,.xlsx,.xls"
              style={{ display: 'none' }}
              onChange={handleFileChange}
            />

            {/* Text input */}
            <input
              ref={inputRef}
              className="chatbot-input"
              type="text"
              placeholder={listening ? 'Listening…' : PLACEHOLDERS[lang]}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKey}
              aria-label="Chat input"
            />

            {/* Voice button */}
            {hasSpeech && (
              <button
                className={`chatbot-icon-btn chatbot-mic-btn${listening ? ' chatbot-mic-btn--active' : ''}`}
                onClick={toggleVoice}
                title={listening ? 'Stop listening' : 'Voice input'}
                aria-label={listening ? 'Stop listening' : 'Start voice input'}
              >
                🎙
              </button>
            )}

            {/* Send */}
            <button
              className="chatbot-send"
              onClick={() => sendMessage()}
              disabled={!input.trim() && pendingFiles.length === 0}
              aria-label="Send"
            >
              ➤
            </button>
          </div>
        </div>
      )}
    </>
  )
}
