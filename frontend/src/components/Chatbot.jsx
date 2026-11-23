import { useState, useRef, useEffect, useCallback } from 'react'

import './Chatbot.css'

import useLang from '../useLang'

import { setLang as setGlobalLang } from '../i18n'



// ==================================================
// MULTI-LANGUAGE CHATBOT — IntelliWatch Assistant
// Features:
//   - Dify Chatflow integration for authenticated users
//   - Local responses for Offline Demo
//   - Multilingual interface
//   - Photo/document attachment previews
//   - Voice input (Web Speech API)
//   - Voice output (TTS)
//   - Quick prompts
//   - Conversation memory through Dify conversation_id
// ==================================================
const API_BASE = (

  import.meta.env.VITE_API_URL || 'http://localhost:8000'

).replace(/\/+$/, '')



const LANGUAGES = [

  { code: 'en', label: 'EN', name: 'English', flag: '🇬🇧' },

  { code: 'hi', label: 'HI', name: 'हिन्दी', flag: '🇮🇳' },

  { code: 'kn', label: 'KN', name: 'ಕನ್ನಡ', flag: '🇮🇳' },

  { code: 'ta', label: 'TA', name: 'தமிழ்', flag: '🇮🇳' },

  { code: 'te', label: 'TE', name: 'తెలుగు', flag: '🇮🇳' },

]



const LANG_LOCALE = {

  en: 'en-IN',

  hi: 'hi-IN',

  kn: 'kn-IN',

  ta: 'ta-IN',

  te: 'te-IN',

}



const LANGUAGE_NAMES = {

  en: 'English',

  hi: 'Hindi',

  kn: 'Kannada',

  ta: 'Tamil',

  te: 'Telugu',

}



// ==================================================
// MULTILINGUAL LOCAL KNOWLEDGE BASE
// ==================================================
// BOLT KNOWLEDGE BASE
// Used only by Offline Demo.
// Authenticated sessions use the Dify Chatflow.
// ==================================================
const KB = {

  en: {

    greeting:
      "Hey! I'm Bolt ⚡ — your IntelliWatch assistant. I can help with the project, sensors, ML, your role, or just have a general chat. What's on your mind?",

    fallback:
      "I'm not sure about that one. Try asking about IntelliWatch, sensors, your role, or anything else — I'll do my best.",

    about:
      'IntelliWatch is a real-time condition-monitoring and safety-actuation system for industrial equipment. It reads vibration, temperature, and current from physical sensors, runs ML inference to classify equipment health as NORMAL, WARNING, or CRITICAL, and automatically fires control signals — shutting down or de-rating the equipment and updating the LCD display. The full stack is React (Vercel) + FastAPI (Railway) + Neon Postgres.',

    vibration:
      'The vibration sensor (ADXL345) measures equipment shake and oscillation. IntelliWatch uses ISO 10816-3 as a reference — warning is typically around 4.5 mm/s RMS, critical around 7.1 mm/s RMS for general industrial motors. Anomalies can mean bearing faults, rotor unbalance, or shaft misalignment.',

    temperature:
      'The DS18B20 uses the 1-Wire protocol. Temperature limits depend on motor insulation class — Class B allows up to 130 °C winding temperature. IntelliWatch warns around 70 °C ambient + motor rise and flags critical around 85 °C.',

    current:
      'The ACS712 current sensor uses the Hall effect. IntelliWatch warns at 110% of full-load amperage (FLA) and flags critical at 125% FLA. Calibrate it to your specific motor for accurate readings.',

    iot:
      'IntelliWatch connects sensors via a Raspberry Pi using GPIO, I²C (ADXL345 vibration), 1-Wire (DS18B20 temperature), and SPI/ADC (ACS712 current). The Pi pushes readings over HTTP to the Railway backend. The LCD (HD44780) and relay board are actuators driven by the backend control signals.',

    alert:
      'Alerts appear when sensor readings cross warning or critical thresholds. Click ✓ to confirm an anomaly (this trains the ML model) or ✕ to dismiss as a false positive. CRITICAL alerts trigger an automatic SHUTDOWN — the relay de-energises and the LCD shows SYSTEM: STOP.',

    roles:
      'Three roles: OPERATOR (read-only — sees live data and why a device stopped), MAINTENANCE ENGINEER (can dispatch SHUTDOWN / DE_RATE / RUN control signals), ADMIN (everything — plus user management and device registration).',

    ml:
      'IntelliWatch uses a bearing-fault ML model trained on the KAIST dataset. It classifies vibration signatures for inner-race faults (BPFI), outer-race faults (BPFO), ball faults, and normal operation. The browser-side ML engine also runs an adaptive EMA anomaly scorer that learns your specific equipment\'s baseline over time.',

    status:
      'System status is NORMAL (all sensors healthy), WARNING (one or more sensors elevated — DE_RATE signal sent), or CRITICAL (immediate fault — SHUTDOWN signal sent, equipment stopped). The WebSocket stream updates the dashboard in real time.',

    explorer:
      'The 3D Explorer is a virtual workbench where you can drag and place IntelliWatch hardware components — sensors, Pi, relay board, LCD — to plan your physical setup before wiring.',

    leaderboard:
      'The TenderWatch Leaderboard ranks organisations by maintenance performance indicators. It\'s a demonstration feature showing how IntelliWatch data could feed an industry-wide benchmarking system.',

    deployment:
      'IntelliWatch is deployed on three platforms: Vercel (React frontend), Railway (FastAPI backend with Python 3.11), and Neon Postgres (19-table database). The backend URL is https://intelliwatch-backend-production.up.railway.app and the frontend is https://frontend-five-kappa-31.vercel.app.',

    general_thanks:
      "You're welcome! Anything else I can help with?",

    general_how_are_you:
      "I'm running great — all systems nominal! How can I help you today?",

    general_weather:
      "I don't have live weather data, but I can tell you that temperature anomalies in your industrial equipment are something I watch closely! For actual weather, check a service like weather.com.",

    general_joke:
      "Why did the engineer bring a ladder to work? Because they heard the vibration levels were through the roof! 😄 (IntelliWatch would have flagged that as CRITICAL.)",

    general_time:
      `The current time in your browser is ${new Date().toLocaleTimeString()}. Need help with something IntelliWatch-related?`,

    general_math:
      "I can do basic arithmetic! Try asking me something like 'what is 15% of 240' and I'll calculate it for you.",

    attachment_ack:
      "I can see the attached file, but Offline Demo can't send its contents to an AI service. Describe what's in it and I'll help with what I know.",

    voice_ack:
      'Got your voice input! Send the text when you\'re ready.',

  },

  hi: {

    greeting:
      'नमस्ते! मैं Bolt ⚡ हूँ। IntelliWatch, सेंसर, ML, या कोई भी सवाल — बताइए, कैसे मदद करूँ?',

    fallback:
      'मुझे इस सवाल का पक्का जवाब नहीं पता। कृपया IntelliWatch, sensors, या अपनी role के बारे में पूछें।',

    about:
      'IntelliWatch एक real-time condition-monitoring system है। यह vibration, temperature और current sensors से data लेकर ML से equipment health classify करता है — NORMAL, WARNING, या CRITICAL — और automatically control signals भेजता है।',

    vibration:
      'ADXL345 vibration sensor कंपन मापता है। ISO 10816-3 के अनुसार warning ~4.5 mm/s RMS और critical ~7.1 mm/s RMS होती है। Anomalies bearing faults, misalignment, या unbalance indicate करती हैं।',

    temperature:
      'DS18B20 sensor 1-Wire protocol use करता है। Class B motors के लिए warning ~70°C और critical ~85°C है।',

    current:
      'ACS712 Hall effect use करता है। Warning 110% FLA पर और critical 125% FLA पर set है।',

    iot:
      'Raspberry Pi के through GPIO, I²C, 1-Wire interfaces use होते हैं। Pi readings को HTTP से Railway backend तक भेजता है।',

    alert:
      'Alerts warning/critical thresholds cross होने पर बनते हैं। ✓ से anomaly confirm करें (ML सीखेगा), ✕ से false positive dismiss करें।',

    roles:
      'ADMIN (सब कुछ), MAINTENANCE ENGINEER (control signals), OPERATOR (read-only — देख सकते हैं कि device क्यों रुका)।',

    ml:
      'KAIST bearing-fault dataset पर trained ML model BPFI, BPFO, ball faults और normal operation classify करता है।',

    status:
      'System status: NORMAL, WARNING (DE_RATE signal), CRITICAL (SHUTDOWN signal — relay off, LCD पर STOP)।',

    explorer:
      '3D Explorer में virtual workbench पर hardware components drag करके setup plan करें।',

    leaderboard:
      'TenderWatch Leaderboard organisations को maintenance performance से rank करता है।',

    deployment:
      'Frontend Vercel पर, Backend Railway पर, Database Neon Postgres पर deploy है।',

    general_thanks: 'आपका स्वागत है! और कुछ पूछना है?',
    general_how_are_you: 'सब systems normal हैं! कैसे help करूँ?',
    general_weather: 'मेरे पास live weather data नहीं है, लेकिन equipment temperature जरूर monitor करता हूँ!',
    general_joke: 'Engineer ने ladder क्यों लाया? क्योंकि vibration levels "through the roof" थीं! 😄',
    general_time: `अभी का समय: ${new Date().toLocaleTimeString('hi-IN')}।`,
    general_math: 'Basic calculations कर सकता हूँ! जैसे "240 का 15% क्या है" पूछें।',
    attachment_ack: 'File देख सकता हूँ, लेकिन Offline Demo में content AI को नहीं भेज सकता।',
    voice_ack: 'Voice input मिला! Text send करें।',

  },

  kn: {

    greeting: 'ನಮಸ್ಕಾರ! ನಾನು Bolt ⚡ — ನಿಮ್ಮ IntelliWatch assistant. ಹೇಗೆ ಸಹಾಯ ಮಾಡಲಿ?',
    fallback: 'ಆ ಪ್ರಶ್ನೆಗೆ ಉತ್ತರ ಗೊತ್ತಿಲ್ಲ. IntelliWatch ಅಥವಾ sensors ಬಗ್ಗೆ ಕೇಳಿ.',
    about: 'IntelliWatch industrial equipment ಅನ್ನು real-time ನಲ್ಲಿ monitor ಮಾಡುತ್ತದೆ ಮತ್ತು anomalies detect ಆದಾಗ automatically control signals ಕಳುಹಿಸುತ್ತದೆ.',
    vibration: 'ADXL345 sensor ಕಂಪನ ಅಳೆಯುತ್ತದೆ. ISO 10816-3 ಪ್ರಕಾರ warning ~4.5 mm/s, critical ~7.1 mm/s.',
    temperature: 'DS18B20 1-Wire protocol ಬಳಸುತ್ತದೆ. Warning ~70°C, critical ~85°C.',
    current: 'ACS712 Hall effect ಬಳಸುತ್ತದೆ. Warning 110% FLA, critical 125% FLA.',
    iot: 'Raspberry Pi GPIO, I²C, 1-Wire ಮೂಲಕ sensors ಸಂಪರ್ಕಿಸುತ್ತದೆ.',
    alert: '✓ anomaly confirm, ✕ false positive dismiss. CRITICAL alert → relay off, LCD STOP.',
    roles: 'ADMIN (ಎಲ್ಲ), MAINTENANCE ENGINEER (control signals), OPERATOR (read-only).',
    ml: 'KAIST dataset ನಲ್ಲಿ trained model bearing faults classify ಮಾಡುತ್ತದೆ.',
    status: 'NORMAL, WARNING (DE_RATE), CRITICAL (SHUTDOWN).',
    explorer: '3D Explorer ನಲ್ಲಿ virtual workbench ಮೇಲೆ hardware plan ಮಾಡಿ.',
    leaderboard: 'TenderWatch Leaderboard organisations rank ಮಾಡುತ್ತದೆ.',
    deployment: 'Frontend Vercel, Backend Railway, Database Neon Postgres.',
    general_thanks: 'ಸ್ವಾಗತ! ಇನ್ನೇನಾದರೂ ಕೇಳಬೇಕೆ?',
    general_how_are_you: 'ಎಲ್ಲ systems normal ಆಗಿದೆ!',
    general_weather: 'Live weather data ಇಲ್ಲ, ಆದರೆ equipment temperature monitor ಮಾಡುತ್ತೇನೆ!',
    general_joke: 'Engineer ladder ಏಕೆ ತಂದರು? Vibration levels "through the roof" ಆಗಿದ್ದವು! 😄',
    general_time: `ಈಗಿನ ಸಮಯ: ${new Date().toLocaleTimeString()}.`,
    general_math: 'Basic calculations ಮಾಡಬಹುದು!',
    attachment_ack: 'File ಕಾಣಿಸುತ್ತಿದೆ, ಆದರೆ Offline Demo ನಲ್ಲಿ AI ಗೆ ಕಳುಹಿಸಲಾಗದು.',
    voice_ack: 'Voice input ಸ್ವೀಕರಿಸಲಾಗಿದೆ!',

  },

  ta: {

    greeting: 'வணக்கம்! நான் Bolt ⚡ — உங்கள் IntelliWatch assistant. எப்படி உதவட்டும்?',
    fallback: 'அந்த கேள்விக்கு பதில் தெரியவில்லை. IntelliWatch அல்லது sensors பற்றி கேளுங்கள்.',
    about: 'IntelliWatch industrial equipment ஐ real-time ல் monitor செய்து anomalies கண்டறிந்து automatically control signals அனுப்புகிறது.',
    vibration: 'ADXL345 sensor அதிர்வு அளவிடுகிறது. ISO 10816-3 படி warning ~4.5 mm/s, critical ~7.1 mm/s.',
    temperature: 'DS18B20 1-Wire protocol பயன்படுத்துகிறது. Warning ~70°C, critical ~85°C.',
    current: 'ACS712 Hall effect பயன்படுத்துகிறது. Warning 110% FLA, critical 125% FLA.',
    iot: 'Raspberry Pi GPIO, I²C, 1-Wire மூலம் sensors இணைக்கிறது.',
    alert: '✓ anomaly உறுதிப்படுத்து, ✕ false positive நிராகரி. CRITICAL → relay off, LCD STOP.',
    roles: 'ADMIN (அனைத்தும்), MAINTENANCE ENGINEER (control signals), OPERATOR (read-only).',
    ml: 'KAIST dataset ல் trained model bearing faults classify செய்கிறது.',
    status: 'NORMAL, WARNING (DE_RATE), CRITICAL (SHUTDOWN).',
    explorer: '3D Explorer ல் virtual workbench ல் hardware plan செய்யுங்கள்.',
    leaderboard: 'TenderWatch Leaderboard organisations rank செய்கிறது.',
    deployment: 'Frontend Vercel, Backend Railway, Database Neon Postgres.',
    general_thanks: 'நன்றி! வேறு எதாவது கேட்கணுமா?',
    general_how_are_you: 'எல்லா systems normal ஆக உள்ளன!',
    general_weather: 'Live weather data இல்லை, ஆனால் equipment temperature monitor செய்கிறேன்!',
    general_joke: 'Engineer ஏன் ladder கொண்டு வந்தார்? Vibration levels "through the roof" ஆக இருந்தன! 😄',
    general_time: `தற்போதைய நேரம்: ${new Date().toLocaleTimeString()}.`,
    general_math: 'Basic calculations செய்யலாம்!',
    attachment_ack: 'File தெரிகிறது, ஆனால் Offline Demo ல் AI க்கு அனுப்ப முடியாது.',
    voice_ack: 'Voice input பெறப்பட்டது!',

  },

  te: {

    greeting: 'నమస్కారం! నేను Bolt ⚡ — మీ IntelliWatch assistant. ఎలా సహాయపడనా?',
    fallback: 'ఆ ప్రశ్నకు జవాబు తెలియదు. IntelliWatch లేదా sensors గురించి అడగండి.',
    about: 'IntelliWatch industrial equipment ని real-time లో monitor చేసి anomalies detect చేసి automatically control signals పంపుతుంది.',
    vibration: 'ADXL345 sensor కంపనం కొలుస్తుంది. ISO 10816-3 ప్రకారం warning ~4.5 mm/s, critical ~7.1 mm/s.',
    temperature: 'DS18B20 1-Wire protocol వాడుతుంది. Warning ~70°C, critical ~85°C.',
    current: 'ACS712 Hall effect వాడుతుంది. Warning 110% FLA, critical 125% FLA.',
    iot: 'Raspberry Pi GPIO, I²C, 1-Wire ద్వారా sensors connect చేస్తుంది.',
    alert: '✓ anomaly confirm, ✕ false positive dismiss. CRITICAL → relay off, LCD STOP.',
    roles: 'ADMIN (అన్నీ), MAINTENANCE ENGINEER (control signals), OPERATOR (read-only).',
    ml: 'KAIST dataset లో trained model bearing faults classify చేస్తుంది.',
    status: 'NORMAL, WARNING (DE_RATE), CRITICAL (SHUTDOWN).',
    explorer: '3D Explorer లో virtual workbench పై hardware plan చేయండి.',
    leaderboard: 'TenderWatch Leaderboard organisations rank చేస్తుంది.',
    deployment: 'Frontend Vercel, Backend Railway, Database Neon Postgres.',
    general_thanks: 'స్వాగతం! మరేమైనా అడగాలా?',
    general_how_are_you: 'అన్ని systems normal గా ఉన్నాయి!',
    general_weather: 'Live weather data లేదు, కానీ equipment temperature monitor చేస్తాను!',
    general_joke: 'Engineer ladder ఎందుకు తెచ్చారు? Vibration levels "through the roof" గా ఉన్నాయి! 😄',
    general_time: `ప్రస్తుత సమయం: ${new Date().toLocaleTimeString()}.`,
    general_math: 'Basic calculations చేయగలను!',
    attachment_ack: 'File కనిపిస్తోంది, కానీ Offline Demo లో AI కి పంపలేను.',
    voice_ack: 'Voice input అందింది!',

  },

}



// ==================================================
// OFFLINE DEMO KEYWORD MATCHING
// ==================================================
function classifyMessage(text) {
  const t = String(text || '').toLowerCase().trim()

  if (!t) return 'fallback'

  // Specific sensor and feature intents must win
  // over broad words such as "what", "system", or "about".

  if (/\b(vibrat|adxl|shake|oscillat|कंपन|ಕಂಪನ|అదురు|அதிர்)\b/.test(t)) {
    return 'vibration'
  }

  if (/\b(temp|heat|ds18|thermal|celsius|degree|तापमान|ಉಷ್ಣ|வெப்ப|ఉష్ణ)\b/.test(t)) {
    return 'temperature'
  }

  if (/\b(motor\s+faults?|motor\s+failure|motor\s+problem|motor\s+anomal|fault\s+(in\s+)?motor|motor\s+health\s+fault)\b/.test(t)) return 'ml'
  if (/\b(current|amp|acs|motor|power|करंट|ಮಿನ್ನ|மின்|విద్యుత్)\b/.test(t)) {
    return 'current'
  }

  if (/\b(alert|log|notif|alarm|warn|critical|threshold|event)\b/.test(t)) {
    return 'alert'
  }

  if (/\b(role|admin|operator|engineer|user|access|login|auth|permission)\b/.test(t)) {
    return 'roles'
  }

  if (/\b(ml|machine learning|model|kaist|fault|bpfi|bpfo|misalign|unbalanc|predict|classif|anomal)\b/.test(t)) {
    return 'ml'
  }

  if (/\b(iot|raspberry|sensor|hardware|connect|wire|gpio|i2c|mqtt|websocket)\b/.test(t)) {
    return 'iot'
  }

  if (/\b(3d|explorer|lab|workbench|component|drag)\b/.test(t)) {
    return 'explorer'
  }

  if (/\b(leader|board|rank|tender|top|org|company|chart)\b/.test(t)) {
    return 'leaderboard'
  }

  if (/\b(status|health|online|offline|live|state)\b/.test(t)) {
    return 'status'
  }

  if (/^\s*(hi|hello|hey|namaste|vanakkam|namaskara|namaskar|help|start)\s*[!.?]*\s*$/.test(t)) {
    return 'greeting'
  }

  if (/\b(intelliwatch|project|overview|explain|what is this system|tell me about the project)\b/.test(t)) {
    return 'about'
  }

  if (/\b(thank|thanks|thank you|dhanyavad|shukriya|nandri|dhanyavaad)\b/.test(t)) {
    return 'general_thanks'
  }

  if (/\b(how are you|how r u|you ok|you good|hows it going|sup bolt)\b/.test(t)) {
    return 'general_how_are_you'
  }

  if (/\b(weather|rain|sunny|forecast|temperature outside|climate)\b/.test(t)) {
    return 'general_weather'
  }

  if (/\b(joke|funny|laugh|humor|pun)\b/.test(t)) {
    return 'general_joke'
  }

  if (/\b(time|clock|what time|current time)\b/.test(t)) {
    return 'general_time'
  }

  if (/\b(calculat|math|plus|minus|multiply|divide|percent|%|sum|add|subtract|\d+\s*[\+\-\*\/]\s*\d+)\b/.test(t)) {
    return 'general_math'
  }

  if (/\b(deploy|deployment|vercel|railway|neon|cloud|hosting|url|link|live)\b/.test(t)) {
    return 'deployment'
  }

  return 'fallback'
}



// ==================================================
// FILE TYPE HELPERS
// ==================================================
function isImage(file) {

  return file.type.startsWith('image/')

}



function fileIcon(file) {

  if (isImage(file)) return '🖼️'

  if (file.type === 'application/pdf') return '📄'

  if (file.name.match(/\.(doc|docx)$/i)) return '📝'

  if (file.name.match(/\.(xls|xlsx)$/i)) return '📊'

  if (file.name.match(/\.(txt|csv|md)$/i)) return '📃'

  return '📎'

}



// ==================================================
// QUICK PROMPTS
// ==================================================
const QUICK_PROMPTS = [

  {

    label: '📡 Vibration',

    key: 'vibration',

    prompt:

      'Explain vibration monitoring in IntelliWatch, including the ADXL345 sensor, how readings are interpreted, and important limitations.',

  },

  {

    label: '🌡️ Temperature',

    key: 'temperature',

    prompt:

      'Explain temperature monitoring in IntelliWatch, including the DS18B20 sensor and how temperature readings should be interpreted.',

  },

  {

    label: '⚡ Current',

    key: 'current',

    prompt:

      'Explain current monitoring in IntelliWatch, including the ACS712 sensor, calibration and interpretation of readings.',

  },

  {

    label: '🔔 Alerts',

    key: 'alert',

    prompt:

      'Explain how alerts, warning levels and critical events work in IntelliWatch.',

  },

]



// ==================================================
// ROBOT AVATAR SVG
// ==================================================
function RobotAvatar({ size = 56, glow = true, pulse = false }) {

  return (

    <svg

      width={size}

      height={size}

      viewBox="0 0 100 100"

      fill="none"

      xmlns="http://www.w3.org/2000/svg"

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

          <feMerge>

            <feMergeNode in="g" />

            <feMergeNode in="SourceGraphic" />

          </feMerge>

        </filter>



        <filter id="softShadow" x="-20%" y="-20%" width="140%" height="140%">

          <feDropShadow

            dx="0"

            dy="2"

            stdDeviation="2"

            floodColor="#000"

            floodOpacity="0.25"

          />

        </filter>

      </defs>



      <circle cx="50" cy="50" r="49" fill="url(#bgGrad)" />

      <circle

        cx="50"

        cy="50"

        r="47"

        fill="none"

        stroke="#3b82f6"

        strokeWidth="1.5"

        strokeOpacity="0.7"

      />



      <rect

        x="31"

        y="62"

        width="38"

        height="26"

        rx="10"

        fill="url(#bodyW)"

        filter="url(#softShadow)"

      />



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



      <rect

        x="24"

        y="18"

        width="52"

        height="46"

        rx="16"

        fill="url(#bodyW)"

        filter="url(#softShadow)"

      />



      <ellipse cx="38" cy="24" rx="8" ry="4" fill="white" fillOpacity="0.35" />

      <rect x="47" y="9" width="6" height="11" rx="3" fill="#d1dde8" />

      <rect x="43" y="6" width="14" height="5" rx="2.5" fill="#1e293b" />

      <rect x="46" y="7" width="8" height="2" rx="1" fill="#38bdf8" filter="url(#glow)" />



      <rect x="29" y="26" width="42" height="30" rx="12" fill="url(#visor)" />

      <ellipse cx="40" cy="31" rx="7" ry="3" fill="white" fillOpacity="0.1" />



      <path

        d="M 35 42 Q 39 36 43 42"

        stroke="url(#eyeL)"

        strokeWidth="2.5"

        fill="none"

        strokeLinecap="round"

        filter="url(#glow)"

      />



      <path

        d="M 47 42 Q 51 36 55 42"

        stroke="url(#eyeR)"

        strokeWidth="2.5"

        fill="none"

        strokeLinecap="round"

        filter="url(#glow)"

      />



      <circle cx="43" cy="40" r="1.2" fill="#a5f3fc" fillOpacity="0.9" />

      <circle cx="55" cy="40" r="1.2" fill="#a5f3fc" fillOpacity="0.9" />



      <ellipse cx="34" cy="46" rx="4.5" ry="2.5" fill="#f472b6" fillOpacity="0.35" />

      <ellipse cx="56" cy="46" rx="4.5" ry="2.5" fill="#f472b6" fillOpacity="0.35" />



      <path

        d="M 38 50 Q 45 56 57 50"

        stroke="#f9a8d4"

        strokeWidth="1.8"

        fill="none"

        strokeLinecap="round"

      />



      <path

        d="M 24 35 Q 50 8 76 35"

        stroke="#1e293b"

        strokeWidth="4"

        fill="none"

        strokeLinecap="round"

      />



      <rect x="18" y="32" width="12" height="16" rx="6" fill="#1e293b" />

      <rect x="20" y="34" width="8" height="12" rx="4" fill="#0f172a" />

      <circle cx="24" cy="40" r="4.5" fill="none" stroke="#38bdf8" strokeWidth="1.2" />

      <circle cx="24" cy="40" r="2" fill="#0891b2" fillOpacity="0.6" />



      <rect x="70" y="32" width="12" height="16" rx="6" fill="#1e293b" />

      <rect x="72" y="34" width="8" height="12" rx="4" fill="#0f172a" />

      <circle cx="76" cy="40" r="4.5" fill="none" stroke="#38bdf8" strokeWidth="1.2" />

      <circle cx="76" cy="40" r="2" fill="#0891b2" fillOpacity="0.6" />



      <path

        d="M 22 48 Q 28 58 38 60"

        stroke="#374151"

        strokeWidth="2"

        fill="none"

        strokeLinecap="round"

      />



      <rect x="35" y="57" width="9" height="6" rx="3" fill="#1e293b" />

      <rect x="36.5" y="58" width="6" height="4" rx="2" fill="#0891b2" fillOpacity="0.7" />

      <circle cx="40" cy="60" r="1.2" fill="#38bdf8" filter="url(#glow)" />

    </svg>

  )

}



// ==================================================
// ATTACHMENT PREVIEW
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

        <span className="attach-file-size">

          {(file.size / 1024).toFixed(1)} KB

        </span>

      </div>

    </div>

  )

}



// ==================================================
// MAIN CHATBOT COMPONENT
// ==================================================
export default function Chatbot({

  token,

  isDemoSession = false,

}) {

  const [open, setOpen] = useState(false)

    // ── Movable Bolt launcher ──────────────────────────────
  const [fabPosition, setFabPosition] = useState(null)



  const fabDragRef = useRef({

    dragging: false,

    moved: false,

    offsetX: 0,

    offsetY: 0,

    startX: 0,

    startY: 0,

  })



  function handleFabPointerDown(event) {

    if (!event.isPrimary || event.button !== 0) return



    const button = event.currentTarget

    const rect = button.getBoundingClientRect()



    fabDragRef.current = {

      dragging: true,

      moved: false,

      offsetX: event.clientX - rect.left,

      offsetY: event.clientY - rect.top,

      startX: event.clientX,

      startY: event.clientY,

    }



    setFabPosition({

      x: rect.left,

      y: rect.top,

    })



    button.setPointerCapture(event.pointerId)

  }



  function handleFabPointerMove(event) {

    const drag = fabDragRef.current



    if (!drag.dragging) return



    const button = event.currentTarget

    const rect = button.getBoundingClientRect()



    const maxX = Math.max(0, window.innerWidth - rect.width)

    const maxY = Math.max(0, window.innerHeight - rect.height)



    const x = Math.max(

      0,

      Math.min(event.clientX - drag.offsetX, maxX)

    )



    const y = Math.max(

      0,

      Math.min(event.clientY - drag.offsetY, maxY)

    )



    if (

      Math.abs(event.clientX - drag.startX) > 5 ||

      Math.abs(event.clientY - drag.startY) > 5

    ) {

      drag.moved = true

    }



    setFabPosition({ x, y })

  }



  function handleFabPointerUp(event) {

    const button = event.currentTarget

    const drag = fabDragRef.current



    drag.dragging = false



    if (button.hasPointerCapture(event.pointerId)) {

      button.releasePointerCapture(event.pointerId)

    }

  }



  function handleFabPointerCancel() {

    fabDragRef.current.dragging = false

  }



  function handleFabClick(event) {

    if (fabDragRef.current.moved) {

      fabDragRef.current.moved = false

      event.preventDefault()

      event.stopPropagation()

      return

    }



    setOpen(value => !value)

  }

  const globalLang = useLang()

  const [lang, setLang] = useState(globalLang)



  // Tracks the last global language so every language change
  // is handled exactly once, regardless of where it originated.
  const previousGlobalLangRef = useRef(globalLang)

  const languageChangeVersionRef = useRef(0)



  const [input, setInput] = useState('')

  const [messages, setMessages] = useState([])

  const [typing, setTyping] = useState(false)

  const [showLang, setShowLang] = useState(false)



  // Attachment state
  const [pendingFiles, setPendingFiles] = useState([])

  const fileInputRef = useRef(null)



  // Voice-input state
  const [listening, setListening] = useState(false)

  const [voiceError, setVoiceError] = useState('')

  const [interimText, setInterimText] = useState('')

  const recognitionRef = useRef(null)



  // Voice-output state
  const [ttsEnabled, setTtsEnabled] = useState(false)



  // Conversation and request state
  const conversationIdRef = useRef(null)

  const requestControllerRef = useRef(null)

  const requestInProgressRef = useRef(false)



  const messagesEndRef = useRef(null)

  const inputRef = useRef(null)



  const isOfflineDemo =

    Boolean(isDemoSession) || token === 'demo-offline'



  // ── TTS helper ──────────────────────────────────────────────────────────
  const speak = useCallback((text) => {

    if (!ttsEnabled || !window.speechSynthesis || !text) return



    window.speechSynthesis.cancel()



    const utterance = new SpeechSynthesisUtterance(text)

    utterance.lang = LANG_LOCALE[lang] || 'en-IN'

    utterance.rate = 1.05



    window.speechSynthesis.speak(utterance)

  }, [ttsEnabled, lang])



  // ── Add bot response ─────────────────────────────────────────────────────
  function addBotMessage(text) {

    if (!text) return



    const msg = {

      id: `${Date.now()}-${Math.random()}`,

      role: 'bot',

      text,

    }



    setMessages(prev => [...prev, msg])

    speak(text)

  }



  // ── Permanent global language synchronization ──────────────────────────
  useEffect(() => {

    if (previousGlobalLangRef.current === globalLang) return



    previousGlobalLangRef.current = globalLang

    languageChangeVersionRef.current += 1



    setLang(globalLang)



    // Stop any request made using the previous language.
    requestControllerRef.current?.abort()

    requestControllerRef.current = null

    requestInProgressRef.current = false

    conversationIdRef.current = null



    // Stop speech output from the previous language.
    if (window.speechSynthesis) {

      window.speechSynthesis.cancel()

    }



    // Stop voice recognition using the previous language.
    if (recognitionRef.current) {

      recognitionRef.current.abort()

      recognitionRef.current = null

    }



    setListening(false)

    setInterimText('')

    setVoiceError('')

    setTyping(false)

    setShowLang(false)



    // Replace the old conversation with the new-language greeting.
    setMessages([{

      id: `${Date.now()}-${Math.random()}`,

      role: 'bot',

      text: KB[globalLang]?.greeting || KB.en.greeting,

    }])

  }, [globalLang])



  // ── Reset conversation when account/session changes ──────────────────────
  useEffect(() => {

    requestControllerRef.current?.abort()

    requestControllerRef.current = null

    requestInProgressRef.current = false

    conversationIdRef.current = null

    setTyping(false)

  }, [token, isDemoSession])



  // ── Init greeting ────────────────────────────────────────────────────────
  useEffect(() => {

    if (open && messages.length === 0) {

      addBotMessage(KB[lang]?.greeting || KB.en.greeting)

    }



    if (open) {

      const focusTimer = window.setTimeout(

        () => inputRef.current?.focus(),

        120

      )



      return () => window.clearTimeout(focusTimer)

    }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])



  // ── Auto-scroll ──────────────────────────────────────────────────────────
  useEffect(() => {

    messagesEndRef.current?.scrollIntoView({

      behavior: 'smooth',

      block: 'end',

    })

  }, [messages, typing])



  // ── Close language dropdown on outside click ─────────────────────────────
  useEffect(() => {

    if (!showLang) return undefined



    const close = () => setShowLang(false)



    window.addEventListener('mousedown', close)



    return () => {

      window.removeEventListener('mousedown', close)

    }

  }, [showLang])



  // ── Stop voice recognition when panel closes ─────────────────────────────
  useEffect(() => {

    if (!open && recognitionRef.current) {

      recognitionRef.current.abort()

      recognitionRef.current = null

      setListening(false)

      setInterimText('')

    }

  }, [open])



  // ── Cleanup on unmount ───────────────────────────────────────────────────
  useEffect(() => {

    return () => {

      requestControllerRef.current?.abort()



      if (recognitionRef.current) {

        recognitionRef.current.abort()

      }



      if (window.speechSynthesis) {

        window.speechSynthesis.cancel()

      }

    }

  }, [])



  // ── Local Offline Demo response ──────────────────────────────────────────
  function getOfflineResponse(text, hasFiles) {

    if (!text && hasFiles) {

      return KB[lang].attachment_ack || KB.en.attachment_ack

    }

    const t = String(text || '').toLowerCase().trim()
    const topic = classifyMessage(text)

    // Sub-intent detection: return a more specific answer
    // within the same topic so different questions get
    // different responses rather than the same canned string.

    const sub = {
      vibration: () => {
        if (/\b(limit|threshold|iso|standard|safe|maximum|value)\b/.test(t))
          return KB[lang].vibration_limit || 'Vibration limits follow ISO 10816-3. For general industrial motors the warning threshold is typically 4.5 mm/s RMS and critical is 7.1 mm/s RMS, but actual limits depend on machine class and mounting.'
        if (/\b(sensor|adxl|hardware|pin|wire|connect)\b/.test(t))
          return KB[lang].vibration_sensor || 'The ADXL345 accelerometer connects to the Raspberry Pi over I²C (SDA/SCL). It operates at 3.3 V and measures ±2 g to ±16 g. The IntelliWatch backend reads all three axes (X, Y, Z) and uses the vector magnitude for severity classification.'
        if (/\b(anomal|fault|detect|bearing|unbalanc|misalign)\b/.test(t))
          return KB[lang].vibration_fault || 'Vibration anomalies can indicate bearing faults (BPFI/BPFO frequency patterns), rotor unbalance (1× rotational frequency), or shaft misalignment (2× frequency). IntelliWatch classifies these using the KAIST bearing-fault ML model.'
        return KB[lang].vibration
      },
      temperature: () => {
        if (/\b(limit|threshold|safe|maximum|value|celsius|degree)\b/.test(t))
          return KB[lang].temperature_limit || 'Temperature limits depend on motor insulation class. Class B motors allow up to 130 °C winding temperature. IntelliWatch sets a configurable warning threshold (typically 70 °C for ambient + motor rise) and a critical threshold (typically 85 °C).'
        if (/\b(sensor|ds18|wire|protocol|connect|hardware)\b/.test(t))
          return KB[lang].temperature_sensor || 'The DS18B20 uses the 1-Wire protocol on a single GPIO pin. It needs a 4.7 kΩ pull-up resistor between data and 3.3 V. It provides ±0.5 °C accuracy from −10 °C to +85 °C with a 12-bit resolution.'
        return KB[lang].temperature
      },
      current: () => {
        if (/\b(limit|threshold|overload|safe|maximum|amp)\b/.test(t))
          return KB[lang].current_limit || 'Current limits are based on the motor nameplate full-load amperage (FLA). IntelliWatch warns at 110 % FLA and flags critical at 125 % FLA. The ACS712 must be calibrated to the specific motor for accurate readings.'
        if (/\b(sensor|acs|hall|wire|connect|hardware)\b/.test(t))
          return KB[lang].current_sensor || 'The ACS712 current sensor uses the Hall effect and outputs an analogue voltage proportional to current. It connects to an ADC (e.g. MCP3008) on the Raspberry Pi via SPI. The 5 A module has 185 mV/A sensitivity.'
        return KB[lang].current
      },
      alert: () => {
        if (/\b(clear|dismiss|delete|remove)\b/.test(t))
          return KB[lang].alert_clear || 'Alerts can be cleared using the Clear button in the Alert Log. Each alert also has a ✓ (confirm anomaly) and ✕ (dismiss as false positive) button that sends feedback to the learning system.'
        if (/\b(critical|shutdown|stop|emergency)\b/.test(t))
          return KB[lang].alert_critical || 'A CRITICAL alert triggers an automatic SHUTDOWN control signal — the relay de-energises the equipment and the LCD shows SYSTEM : STOP / STATUS : CRITICAL. Only a Maintenance Engineer or Admin can issue a manual RUN signal to restart.'
        if (/\b(warn|derate|slow|reduce)\b/.test(t))
          return KB[lang].alert_warning || 'A WARNING alert triggers a DE_RATE control signal — the main relay stays on but a de-rate relay activates to reduce equipment speed or load. The LCD shows SYSTEM : DERATE / STATUS : WARNING.'
        return KB[lang].alert
      },
      ml: () => {
        if (/\b(kaist|dataset|train|bearing|bpfi|bpfo)\b/.test(t))
          return KB[lang].ml_kaist || 'IntelliWatch uses the KAIST bearing-fault dataset to train its fault-detection model. It includes vibration signatures for inner-race faults (BPFI), outer-race faults (BPFO), ball faults, and normal operation across multiple motor speeds.'
        if (/\b(accuracy|f1|score|metric|perform)\b/.test(t))
          return KB[lang].ml_accuracy || 'Model accuracy is tracked via an F1-score trend stored per model version in the database. The learning system promotes a new model version automatically when the retrained model outperforms the previous one.'
        if (/\b(retrain|recalibrat|learn|update|improve)\b/.test(t))
          return KB[lang].ml_retrain || 'The IntelliWatch learning system accepts operator-verified labels (confirm anomaly / dismiss false positive) and periodically retrains the model. Admin can also trigger a manual recalibration from the dashboard.'
        return KB[lang].ml
      },
      roles: () => {
        if (/\b(admin)\b/.test(t))
          return KB[lang].roles_admin || 'Admin has full access — sensor data, all control signals (SHUTDOWN / DE_RATE / RUN), IoT device registration, user management, model recalibration, and audit log.'
        if (/\b(engineer|maintenance)\b/.test(t))
          return KB[lang].roles_engineer || 'Maintenance Engineer can view all sensor data and dispatch control signals (SHUTDOWN / DE_RATE / RUN). They cannot manage users or register new IoT devices.'
        if (/\b(operator)\b/.test(t))
          return KB[lang].roles_operator || 'Operator has read-only access — they can see live sensor data, the alert log (including why a device was stopped), and the system status. They cannot issue control signals.'
        return KB[lang].roles
      },
    }

    // Math inline calculation
    if (topic === 'general_math') {
      const mathMatch = t.match(/(\d+\.?\d*)\s*([\+\-\*\/x×÷])\s*(\d+\.?\d*)/)
      if (mathMatch) {
        const a = parseFloat(mathMatch[1])
        const op = mathMatch[2]
        const b = parseFloat(mathMatch[3])
        let result
        if (op === '+') result = a + b
        else if (op === '-') result = a - b
        else if (op === '*' || op === 'x' || op === '×') result = a * b
        else if (op === '/' || op === '÷') result = b !== 0 ? a / b : 'undefined (division by zero)'
        if (result !== undefined) return `${a} ${op} ${b} = ${result}`
      }
      const pctMatch = t.match(/(\d+\.?\d*)%?\s*(?:of|percent of|%\s*of)\s*(\d+\.?\d*)/)
      if (pctMatch) {
        const pct = parseFloat(pctMatch[1])
        const num = parseFloat(pctMatch[2])
        return `${pct}% of ${num} = ${(pct / 100 * num).toFixed(2)}`
      }
      return KB[lang].general_math || KB.en.general_math
    }

    const handler = sub[topic]
    if (handler) return handler()

    return KB[lang][topic] || KB[lang].fallback

  }



  // ── Attachment limitation message ────────────────────────────────────────
  function getAttachmentNotice() {

    const notices = {

      en: 'Note: I received your message, but the attached file contents were not sent to the AI service. File-content analysis has not been connected yet.',

      hi: 'ध्यान दें: आपका संदेश प्राप्त हुआ, लेकिन attached file की सामग्री AI service तक नहीं भेजी गई। File-content analysis अभी connect नहीं किया गया है।',

      kn: 'ಸೂಚನೆ: ನಿಮ್ಮ ಸಂದೇಶ ಸ್ವೀಕರಿಸಲಾಗಿದೆ. ಆದರೆ attached file ವಿಷಯವನ್ನು AI service ಗೆ ಕಳುಹಿಸಲಾಗಿಲ್ಲ. File-content analysis ಇನ್ನೂ ಸಂಪರ್ಕಗೊಂಡಿಲ್ಲ.',

      ta: 'குறிப்பு: உங்கள் செய்தி பெறப்பட்டது. ஆனால் attached file உள்ளடக்கம் AI service க்கு அனுப்பப்படவில்லை. File-content analysis இன்னும் இணைக்கப்படவில்லை.',

      te: 'గమనిక: మీ సందేశం అందింది. కానీ attached file content AI service కు పంపబడలేదు. File-content analysis ఇంకా అనుసంధానించబడలేదు.',

    }



    return notices[lang] || notices.en

  }



  // ── Send message to Dify through authenticated backend ───────────────────
  async function sendMessage(overrideText) {

    const text = (overrideText ?? input).trim()

    const filesToSend = [...pendingFiles]

    const hasFiles = filesToSend.length > 0



    if ((!text && !hasFiles) || requestInProgressRef.current) {

      return

    }



    const requestLanguage = lang

    const requestLanguageVersion = languageChangeVersionRef.current



    const userMessage = {

      id: `${Date.now()}-${Math.random()}`,

      role: 'user',

      text: text || null,

      files: hasFiles ? filesToSend : null,

    }



    setMessages(prev => [...prev, userMessage])

    setInput('')

    setPendingFiles([])

    setTyping(true)



    // Offline Demo remains independent of the backend and Dify.
    if (isOfflineDemo) {

      requestInProgressRef.current = true

      const response = getOfflineResponse(text, hasFiles)

      window.setTimeout(() => {
        try {
          // Ignore a response belonging to an older language.
          if (
            requestLanguageVersion !== languageChangeVersionRef.current
          ) {
            return
          }

          addBotMessage(response)
        } finally {
          requestInProgressRef.current = false
          setTyping(false)
        }
      }, 500 + Math.random() * 500)

      return
    }
    // A valid IntelliWatch login is required for the protected AI endpoint.
    if (!token) {

      addBotMessage('Please sign in to IntelliWatch to use Bolt AI.')

      setTyping(false)

      return

    }



    // The attachment preview is retained, but file contents are not uploaded yet.
    if (!text) {

      addBotMessage(getAttachmentNotice())

      setTyping(false)

      return

    }



    requestInProgressRef.current = true



    const controller = new AbortController()

    requestControllerRef.current = controller



    try {

      const languageName = LANGUAGE_NAMES[requestLanguage] || 'English'



      const queryWithLanguage = [

        `Please respond in ${languageName}.`,

        'Use this as a response-language preference.',

        '',

        text,

      ].join('\n')



      const response = await fetch(`${API_BASE}/chatbot/message`, {

        method: 'POST',

        headers: {

          'Content-Type': 'application/json',

          Authorization: `Bearer ${token}`,

        },

        body: JSON.stringify({

          query: queryWithLanguage,

          language: requestLanguage,

          conversation_id: conversationIdRef.current,

        }),

        signal: controller.signal,

      })



      const result = await response.json().catch(() => null)



      // Ignore any result that belongs to an earlier language.
      if (

        requestLanguageVersion !== languageChangeVersionRef.current

      ) {

        return

      }



      if (!response.ok) {

        const detail =

          typeof result?.detail === 'string'

            ? result.detail

            : 'Bolt could not process your message. Please try again.'



        throw new Error(detail)

      }



      if (

        !result ||

        typeof result.answer !== 'string' ||

        !result.answer.trim()

      ) {

        throw new Error('Bolt received an empty response. Please try again.')

      }



      if (

        typeof result.conversation_id === 'string' &&

        result.conversation_id.trim()

      ) {

        conversationIdRef.current = result.conversation_id

      }



      addBotMessage(result.answer.trim())



      if (hasFiles) {

        addBotMessage(getAttachmentNotice())

      }

    } catch (error) {

      if (error?.name === 'AbortError') {

        return

      }



      if (

        requestLanguageVersion !== languageChangeVersionRef.current

      ) {

        return

      }



      const message =

        error instanceof TypeError

          ? 'Bolt could not connect to the IntelliWatch backend. Check that the backend is running and reachable.'

          : (error instanceof Error ? error.message : '') || 'Something went wrong while contacting Bolt AI.'



      addBotMessage(message)

    } finally {

      if (requestControllerRef.current === controller) {

        requestControllerRef.current = null

        requestInProgressRef.current = false

        setTyping(false)

      }

    }

  }



  // ── Keyboard handling ────────────────────────────────────────────────────
  function handleKey(event) {

    if (event.key === 'Enter' && !event.shiftKey) {

      event.preventDefault()

      sendMessage()

    }

  }



  // ── Language change ──────────────────────────────────────────────────────
  function handleLangChange(code) {

    if (!LANGUAGES.some(language => language.code === code)) return



    setShowLang(false)



    // The global synchronization effect handles the actual reset.
    if (code === globalLang) return



    setGlobalLang(code)

  }



  // ── File attachment handling ─────────────────────────────────────────────
  function handleFileChange(event) {

    const files = Array.from(event.target.files || [])



    if (!files.length) return



    files.forEach(file => {

      if (isImage(file)) {

        const reader = new FileReader()



        reader.onload = (loadEvent) => {

          setPendingFiles(prev => [

            ...prev,

            {

              file,

              dataUrl: loadEvent.target.result,

            },

          ])

        }



        reader.onerror = () => {

          setPendingFiles(prev => [

            ...prev,

            {

              file,

              dataUrl: null,

            },

          ])

        }



        reader.readAsDataURL(file)

      } else {

        setPendingFiles(prev => [

          ...prev,

          {

            file,

            dataUrl: null,

          },

        ])

      }

    })



    event.target.value = ''

  }



  function removePendingFile(index) {

    setPendingFiles(prev => prev.filter((_, i) => i !== index))

  }



  // ── Voice input (Web Speech API) ─────────────────────────────────────────
  const SpeechRecognition =

    typeof window !== 'undefined'

      ? window.SpeechRecognition || window.webkitSpeechRecognition

      : null



  const hasSpeech = Boolean(SpeechRecognition)



  function toggleVoice() {

    setVoiceError('')



    if (listening) {

      recognitionRef.current?.stop()

      setListening(false)

      setInterimText('')

      return

    }



    if (!hasSpeech) {

      setVoiceError('Voice input is not supported in this browser.')

      return

    }



    try {

      const recognition = new SpeechRecognition()



      recognition.lang = LANG_LOCALE[lang] || 'en-IN'

      recognition.interimResults = true

      recognition.continuous = false

      recognition.maxAlternatives = 1



      recognition.onstart = () => {

        setListening(true)

        setInterimText('')

      }



      recognition.onend = () => {

        setListening(false)

        setInterimText('')

      }



      recognition.onerror = (event) => {

        setListening(false)

        setInterimText('')



        if (event.error !== 'aborted') {

          setVoiceError(`Mic error: ${event.error}`)

        }

      }



      recognition.onresult = (event) => {

        let finalText = ''

        let interim = ''



        for (

          let index = event.resultIndex;

          index < event.results.length;

          index++

        ) {

          const transcript = event.results[index][0].transcript



          if (event.results[index].isFinal) {

            finalText += transcript

          } else {

            interim += transcript

          }

        }



        if (interim) {

          setInterimText(interim)

        }



        if (finalText.trim()) {

          setInterimText('')

          setInput(prev => (

            prev ? `${prev} ${finalText.trim()}` : finalText.trim()

          ))

          recognition.stop()

        }

      }



      recognitionRef.current = recognition

      recognition.start()

    } catch (error) {

      setListening(false)

      setVoiceError(

        error.message || 'Unable to start voice recognition.'

      )

    }

  }



  // ── TTS toggle ───────────────────────────────────────────────────────────
  function toggleTts() {

    if (ttsEnabled && window.speechSynthesis) {

      window.speechSynthesis.cancel()

    }



    setTtsEnabled(value => !value)

  }



  // ── Quick prompt handling ────────────────────────────────────────────────
  function handleQuickPrompt(prompt) {

    sendMessage(prompt)

  }



  // ── Display values ──────────────────────────────────────────────────────
  const currentLang =

    LANGUAGES.find(language => language.code === lang) || LANGUAGES[0]



  const PLACEHOLDERS = {

    en: 'Ask Bolt anything…',

    hi: 'Bolt से कुछ भी पूछें…',

    kn: 'Bolt ಅನ್ನು ಏನಾದರೂ ಕೇಳಿ…',

    ta: 'Bolt-இடம் ஏதாவது கேளுங்கள்…',

    te: 'Bolt ను ఏదైనా అడగండి…',

  }



  const sendDisabled =

    typing ||

    (!input.trim() && pendingFiles.length === 0)



  // ==================================================
  // RENDER
  // ==================================================
  return (

    <>

      {/* ── Floating trigger button ── */}

            <button

        className={`chatbot-fab ${open ? 'chatbot-fab-open' : ''}`}

        onPointerDown={handleFabPointerDown}

        onPointerMove={handleFabPointerMove}

        onPointerUp={handleFabPointerUp}

        onPointerCancel={handleFabPointerCancel}

        onClick={handleFabClick}

        style={

          fabPosition

            ? {

                position: 'fixed',

                left: `${fabPosition.x}px`,

                top: `${fabPosition.y}px`,

                right: 'auto',

                bottom: 'auto',

                touchAction: 'none',

                cursor: fabDragRef.current.dragging ? 'grabbing' : 'grab',

              }

            : {

                touchAction: 'none',

                cursor: 'grab',

              }

        }

        aria-label="Open IntelliWatch Assistant"

        title="Drag Bolt to move — click to chat"

        type="button"

      >

        <RobotAvatar size={46} glow pulse={!open} />



        {!open && (

          <span className="chatbot-fab-badge">AI</span>

        )}

      </button>



      {/* ── Chat panel ── */}



      {open && (

        <div

          className="chatbot-panel"

          role="dialog"

          aria-label="IntelliWatch Chatbot"

          aria-modal="false"

        >

          {/* Header */}



          <div className="chatbot-header">

            <div className="chatbot-header-left">

              <RobotAvatar size={36} glow />



              <div>

                <span className="chatbot-name">Bolt</span>

                <span className="chatbot-tagline">

                  IntelliWatch Assistant

                </span>

              </div>

            </div>



            <div className="chatbot-header-right">

              {/* TTS toggle */}



              <button

                className={`chatbot-icon-btn${ttsEnabled ? ' chatbot-icon-btn--active' : ''}`}

                onClick={toggleTts}

                title={ttsEnabled ? 'Mute voice responses' : 'Enable voice responses'}

                aria-label={ttsEnabled ? 'Mute' : 'Unmute'}

                type="button"

              >

                {ttsEnabled ? '🔊' : '🔇'}

              </button>



              {/* Language selector */}



              <div

                className="lang-selector-wrap"

                onMouseDown={event => event.stopPropagation()}

              >

                <button

                  className="lang-btn"

                  onClick={() => setShowLang(value => !value)}

                  title="Change language"

                  aria-label="Select language"

                  type="button"

                >

                  {currentLang.flag} {currentLang.label}

                  <span className="lang-chevron">

                    {showLang ? '▲' : '▼'}

                  </span>

                </button>



                {showLang && (

                  <div className="lang-dropdown">

                    {LANGUAGES.map(language => (

                      <button

                        key={language.code}

                        className={`lang-option ${language.code === lang ? 'lang-active' : ''}`}

                        onClick={() => handleLangChange(language.code)}

                        type="button"

                      >

                        <span>{language.flag}</span>

                        <span className="lang-opt-code">

                          {language.label}

                        </span>

                        <span className="lang-opt-name">

                          {language.name}

                        </span>

                      </button>

                    ))}

                  </div>

                )}

              </div>



              {/* Close */}



              <button

                className="chatbot-close"

                onClick={() => setOpen(false)}

                aria-label="Close chat"

                type="button"

              >

                ✕

              </button>

            </div>

          </div>



          {/* Messages */}



          <div className="chatbot-messages">

            {messages.map(message => (

              <div

                key={message.id}

                className={`chat-msg chat-msg-${message.role}`}

              >

                {message.role === 'bot' && (

                  <span className="chat-avatar">

                    <RobotAvatar size={24} glow={false} />

                  </span>

                )}



                <div className="chat-bubble">

                  {message.text && <span>{message.text}</span>}



                  {message.files && message.files.length > 0 && (

                    <div

                      className={`chat-attachments${message.text ? ' chat-attachments--below' : ''}`}

                    >

                      {message.files.map((fileItem, index) => (

                        <AttachmentPreview

                          key={`${fileItem.file.name}-${index}`}

                          file={fileItem.file}

                          dataUrl={fileItem.dataUrl}

                        />

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

                  <span />

                  <span />

                  <span />

                </div>

              </div>

            )}



            <div ref={messagesEndRef} />

          </div>



          {/* Quick prompts */}



          <div className="chatbot-chips">

            {QUICK_PROMPTS.map(prompt => (

              <button

                key={prompt.key}

                className="chip"

                onClick={() => handleQuickPrompt(prompt.prompt)}

                disabled={typing}

                type="button"

              >

                {prompt.label}

              </button>

            ))}

          </div>



          {/* Pending file previews */}



          {pendingFiles.length > 0 && (

            <div className="chatbot-pending-files">

              {pendingFiles.map((fileItem, index) => (

                <div

                  key={`${fileItem.file.name}-${index}`}

                  className="pending-file-chip"

                >

                  <span className="pending-file-icon">

                    {fileIcon(fileItem.file)}

                  </span>



                  <span className="pending-file-name">

                    {fileItem.file.name}

                  </span>



                  <button

                    className="pending-file-remove"

                    onClick={() => removePendingFile(index)}

                    aria-label="Remove attachment"

                    type="button"

                  >

                    ×

                  </button>

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



              <button

                onClick={() => setVoiceError('')}

                aria-label="Dismiss"

                type="button"

              >

                ×

              </button>

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

              type="button"

              disabled={typing}

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

              placeholder={

                listening ? 'Listening…' : PLACEHOLDERS[lang]

              }

              value={input}

              onChange={event => setInput(event.target.value)}

              onKeyDown={handleKey}

              aria-label="Chat input"

              disabled={typing}

            />



            {/* Voice button */}



            {hasSpeech && (

              <button

                className={`chatbot-icon-btn chatbot-mic-btn${listening ? ' chatbot-mic-btn--active' : ''}`}

                onClick={toggleVoice}

                title={listening ? 'Stop listening' : 'Voice input'}

                aria-label={listening ? 'Stop listening' : 'Start voice input'}

                type="button"

                disabled={typing}

              >

                🎙

              </button>

            )}



            {/* Send */}



            <button

              className="chatbot-send"

              onClick={() => sendMessage()}

              disabled={sendDisabled}

              aria-label="Send"

              type="button"

            >

              ➤

            </button>

          </div>

        </div>

      )}

    </>

  )

}

