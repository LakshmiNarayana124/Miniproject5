import { useState } from 'react'
import useLang from '../useLang'
import './AboutPage.css'

const CONTENT = {
  en: {
    title: 'About IntelliWatch',
    subtitle: 'Real-Time Anomaly Detection & Decision Support System',
    objectives: 'Our Objectives',
    protection: 'Protective Action System',
    sensors: 'Supported Sensors',
    tech: 'Technology Stack',
    faq: 'Frequently Asked Questions',
    feedback: 'Share Your Feedback',
  },
  hi: {
    title: 'IntelliWatch के बारे में',
    subtitle: 'रियल-टाइम असामान्यता पहचान और निर्णय सहायता प्रणाली',
    objectives: 'हमारे उद्देश्य',
    protection: 'सुरक्षा कार्रवाई प्रणाली',
    sensors: 'समर्थित Sensors',
    tech: 'Technology Stack',
    faq: 'अक्सर पूछे जाने वाले प्रश्न',
    feedback: 'अपनी प्रतिक्रिया साझा करें',
  },
  kn: {
    title: 'IntelliWatch ಕುರಿತು',
    subtitle: 'ರಿಯಲ್-ಟೈಮ್ ಅಸಾಮಾನ್ಯತೆ ಪತ್ತೆ ಮತ್ತು ನಿರ್ಧಾರ ಸಹಾಯ ವ್ಯವಸ್ಥೆ',
    objectives: 'ನಮ್ಮ ಉದ್ದೇಶಗಳು',
    protection: 'ರಕ್ಷಣಾತ್ಮಕ ಕಾರ್ಯ ವ್ಯವಸ್ಥೆ',
    sensors: 'ಬೆಂಬಲಿತ Sensors',
    tech: 'Technology Stack',
    faq: 'ಪದೇ ಪದೇ ಕೇಳಲಾಗುವ ಪ್ರಶ್ನೆಗಳು',
    feedback: 'ನಿಮ್ಮ ಅಭಿಪ್ರಾಯ ಹಂಚಿಕೊಳ್ಳಿ',
  },
  ta: {
    title: 'IntelliWatch பற்றி',
    subtitle: 'நிகழ்நேர அசாதாரண கண்டறிதல் மற்றும் முடிவு ஆதரவு அமைப்பு',
    objectives: 'எங்கள் நோக்கங்கள்',
    protection: 'பாதுகாப்பு செயல்பாட்டு அமைப்பு',
    sensors: 'ஆதரிக்கப்படும் Sensors',
    tech: 'Technology Stack',
    faq: 'அடிக்கடி கேட்கப்படும் கேள்விகள்',
    feedback: 'உங்கள் கருத்தைப் பகிரவும்',
  },
  te: {
    title: 'IntelliWatch గురించి',
    subtitle: 'రియల్-టైమ్ అసాధారణ గుర్తింపు మరియు నిర్ణయ సహాయక వ్యవస్థ',
    objectives: 'మా లక్ష్యాలు',
    protection: 'రక్షణ చర్యల వ్యవస్థ',
    sensors: 'మద్దతు ఉన్న Sensors',
    tech: 'Technology Stack',
    faq: 'తరచుగా అడిగే ప్రశ్నలు',
    feedback: 'మీ అభిప్రాయాన్ని పంచుకోండి',
  },
}

const OBJECTIVES = {
  en: [
    'Monitor equipment health using sensor readings.',
    'Identify abnormal operating patterns using machine learning.',
    'Generate alerts to help operators respond to equipment issues.',
    'Support maintenance decisions using equipment information and historical data.',
  ],
  hi: [
    'Sensor readings की मदद से equipment की स्थिति monitor करना।',
    'Machine learning से असामान्य operating patterns पहचानना।',
    'Equipment समस्याओं पर operators को alerts देना।',
    'Equipment information और historical data से maintenance decisions में सहायता करना।',
  ],
  kn: [
    'Sensor readings ಮೂಲಕ equipment ಆರೋಗ್ಯವನ್ನು monitor ಮಾಡುವುದು.',
    'Machine learning ಮೂಲಕ ಅಸಾಮಾನ್ಯ operating patterns ಗುರುತಿಸುವುದು.',
    'Equipment ಸಮಸ್ಯೆಗಳ ಬಗ್ಗೆ operators ಗೆ alerts ನೀಡುವುದು.',
    'Equipment ಮಾಹಿತಿ ಮತ್ತು historical data ಮೂಲಕ maintenance ನಿರ್ಧಾರಗಳಿಗೆ ಸಹಾಯ ಮಾಡುವುದು.',
  ],
  ta: [
    'Sensor readings மூலம் equipment நிலையை கண்காணித்தல்.',
    'Machine learning மூலம் அசாதாரண செயல்பாட்டு முறைகளை அடையாளம் காணுதல்.',
    'Equipment பிரச்சினைகள் குறித்து operators க்கு alerts வழங்குதல்.',
    'Equipment தகவல் மற்றும் historical data மூலம் maintenance முடிவுகளுக்கு உதவுதல்.',
  ],
  te: [
    'Sensor readings ద్వారా equipment ఆరోగ్యాన్ని monitor చేయడం.',
    'Machine learning ద్వారా అసాధారణ operating patterns గుర్తించడం.',
    'Equipment సమస్యల గురించి operators కు alerts ఇవ్వడం.',
    'Equipment సమాచారం మరియు historical data ద్వారా maintenance నిర్ణయాలకు సహాయపడడం.',
  ],
}

const FAQ = {
  en: [
    {
      q: 'What faults can IntelliWatch detect?',
      a: 'IntelliWatch analyses vibration, temperature, and current readings to identify abnormal patterns that may indicate bearing faults, shaft misalignment, rotor unbalance, motor overload, or overheating. Detection depends on sensor data and model capability.',
    },
    {
      q: 'What happens when a critical threshold is breached?',
      a: 'When a critical threshold is detected, IntelliWatch can issue an equipment stop command through the connected relay system. The dashboard displays a critical alert and records the event. Actual hardware stopping depends on successful IoT and relay integration.',
    },
    {
      q: 'How does the warning mode protect equipment?',
      a: 'Warning mode identifies readings that have moved beyond normal limits and indicates that attention may be needed. Controlled speed reduction requires a compatible motor controller and hardware integration.',
    },
    {
      q: 'Why is gradual slowdown useful?',
      a: 'Gradually reducing machine speed can help avoid sudden mechanical stress. It also gives operators time to inspect the equipment before the condition becomes more serious.',
    },
    {
      q: 'Can IntelliWatch integrate with SCADA or PLC systems?',
      a: 'IntelliWatch provides backend APIs and real-time communication capabilities. Integration with specific SCADA or PLC systems depends on compatible protocols, adapters, and configuration.',
    },
    {
      q: 'What sensors does IntelliWatch support?',
      a: 'The system is designed to work with the ADXL345 vibration sensor, DS18B20 temperature sensor, and ACS712 current sensor. An ADS1115 ADC can convert the current sensor output for digital processing.',
    },
    {
      q: 'How accurate is anomaly detection?',
      a: 'The machine-learning model uses features from the KAIST bearing fault dataset. Actual detection performance depends on the test conditions, sensor placement, machine type, and quality of incoming data.',
    },
    {
      q: 'What happens if IoT hardware disconnects?',
      a: 'If sensor data is unavailable, IntelliWatch can indicate that it is waiting for an IoT signal. Reliable hardware protection during disconnection depends on the actual relay configuration and independent safety arrangements.',
    },
    {
      q: 'How are user roles structured?',
      a: 'ADMIN manages users and system settings. OPERATOR accesses operational information and alerts. MAINTENANCE ENGINEER accesses maintenance-related information and diagnostic features. Access is controlled through role-based permissions.',
    },
    {
      q: 'How is IntelliWatch different from commercial monitoring platforms?',
      a: 'IntelliWatch is designed as a cost-conscious, flexible monitoring and decision-support system. It combines sensor monitoring, anomaly detection, alerts, and equipment information in one platform.',
    },
    {
      q: 'What is the TenderWatch Leaderboard?',
      a: 'TenderWatch is a leaderboard feature that presents industrial organization information and predictive maintenance maturity scores within IntelliWatch.',
    },
    {
      q: 'Does IntelliWatch support multiple machines?',
      a: 'The current setup is designed around a single-machine monitoring node. Monitoring multiple machines requires suitable hardware nodes and additional system configuration.',
    },
    {
      q: 'What is Equipment Vision?',
      a: 'Equipment Vision helps users identify equipment using a live camera or an uploaded photograph. It makes it easier to understand what a piece of equipment is.',
    },
    {
      q: 'Can I upload an equipment photograph?',
      a: 'Yes. You can upload an equipment image for visual identification and information about the equipment.',
    },
    {
      q: 'Can Equipment Vision use a live camera?',
      a: 'Yes. It can analyse images captured through a live camera to identify visible equipment.',
    },
    {
      q: 'Can Equipment Vision identify equipment damage?',
      a: 'It can help highlight visible signs such as damage, corrosion, or loose connections when they are identifiable in the image. It does not replace a physical inspection by a qualified person.',
    },
    {
      q: 'What is the Laboratory Equipment feature?',
      a: 'The Laboratory Equipment feature helps users learn about common industrial and laboratory equipment, including its purpose, working principle, and applications.',
    },
    {
      q: 'Does IntelliWatch support multiple languages?',
      a: 'Yes. The interface supports English, Hindi, Kannada, Tamil, and Telugu.',
    },
  ],

  hi: [
    { q: 'IntelliWatch कौन सी खराबियाँ पहचान सकता है?', a: 'IntelliWatch कंपन, तापमान और करंट की रीडिंग का विश्लेषण करके bearing faults, shaft misalignment, rotor unbalance, motor overload और overheating जैसी असामान्य स्थितियों की पहचान करने में मदद करता है।' },
    { q: 'Critical threshold पार होने पर क्या होता है?', a: 'Critical threshold मिलने पर IntelliWatch जुड़े हुए relay system के माध्यम से equipment stop command दे सकता है। Dashboard पर critical alert दिखाई देता है और event रिकॉर्ड होता है। वास्तविक hardware stop IoT और relay integration पर निर्भर करता है।' },
    { q: 'Warning mode उपकरण की सुरक्षा कैसे करता है?', a: 'Warning mode बताता है कि readings सामान्य सीमा से बाहर जा रही हैं और जाँच की आवश्यकता हो सकती है। नियंत्रित speed reduction के लिए compatible motor controller और hardware integration आवश्यक है।' },
    { q: 'धीरे-धीरे गति कम करना उपयोगी क्यों है?', a: 'मशीन की गति धीरे-धीरे कम करने से अचानक mechanical stress से बचने में मदद मिल सकती है। इससे operators को मशीन की जाँच करने का समय मिलता है।' },
    { q: 'क्या IntelliWatch SCADA या PLC से जुड़ सकता है?', a: 'IntelliWatch backend APIs और real-time communication सुविधाएँ प्रदान करता है। किसी विशेष SCADA या PLC से integration compatible protocols और configuration पर निर्भर करता है।' },
    { q: 'IntelliWatch कौन से sensors support करता है?', a: 'यह system ADXL345 vibration sensor, DS18B20 temperature sensor और ACS712 current sensor के साथ काम करने के लिए बनाया गया है। ADS1115 ADC current sensor के output को digital रूप में बदल सकता है।' },
    { q: 'Anomaly detection कितनी accurate है?', a: 'Machine-learning model KAIST bearing fault dataset की features का उपयोग करता है। वास्तविक performance sensor placement, machine type और data quality पर निर्भर करती है।' },
    { q: 'IoT hardware disconnect होने पर क्या होता है?', a: 'Sensor data उपलब्ध न होने पर IntelliWatch IoT signal की प्रतीक्षा होने का संकेत दे सकता है। Hardware protection वास्तविक relay configuration और अलग safety arrangements पर निर्भर करती है।' },
    { q: 'User roles कैसे काम करते हैं?', a: 'ADMIN users और system settings manage करता है। OPERATOR operational information और alerts देखता है। MAINTENANCE ENGINEER maintenance और diagnostic सुविधाओं का उपयोग करता है।' },
    { q: 'IntelliWatch commercial monitoring platforms से कैसे अलग है?', a: 'IntelliWatch एक कम लागत वाला flexible monitoring और decision-support system है। यह sensor monitoring, anomaly detection, alerts और equipment information को एक platform में जोड़ता है।' },
    { q: 'TenderWatch Leaderboard क्या है?', a: 'TenderWatch एक leaderboard feature है जो industrial organizations की जानकारी और predictive maintenance maturity scores दिखाता है।' },
    { q: 'क्या IntelliWatch एक साथ कई machines monitor कर सकता है?', a: 'वर्तमान setup एक machine monitoring node के लिए बनाया गया है। कई machines की monitoring के लिए अतिरिक्त hardware nodes और configuration की आवश्यकता होती है।' },
    { q: 'Equipment Vision क्या है?', a: 'Equipment Vision live camera या upload की गई photograph से equipment की पहचान करने में मदद करता है। इससे उपयोगकर्ता समझ सकते हैं कि उपकरण क्या है।' },
    { q: 'क्या मैं equipment की photograph upload कर सकता हूँ?', a: 'हाँ। आप equipment की image upload करके उसकी visual identification और जानकारी प्राप्त कर सकते हैं।' },
    { q: 'क्या Equipment Vision live camera का उपयोग कर सकता है?', a: 'हाँ। यह live camera से प्राप्त images का विश्लेषण करके दिखाई देने वाले equipment की पहचान कर सकता है।' },
    { q: 'क्या Equipment Vision equipment का damage पहचान सकता है?', a: 'Image में स्पष्ट दिखाई देने वाले damage, corrosion या loose connections जैसे संकेतों को highlight करने में मदद कर सकता है। यह qualified person की physical inspection का विकल्प नहीं है।' },
    { q: 'Laboratory Equipment feature क्या है?', a: 'यह feature सामान्य industrial और laboratory equipment, उनके उपयोग, काम करने के तरीके और applications के बारे में जानकारी देता है।' },
    { q: 'क्या IntelliWatch कई भाषाओं को support करता है?', a: 'हाँ। Interface English, Hindi, Kannada, Tamil और Telugu भाषाओं को support करता है।' },
  ],

  kn: [
    { q: 'IntelliWatch ಯಾವ ದೋಷಗಳನ್ನು ಪತ್ತೆ ಮಾಡಬಹುದು?', a: 'ಕಂಪನ, ತಾಪಮಾನ ಮತ್ತು ವಿದ್ಯುತ್ ಪ್ರವಾಹದ readings ವಿಶ್ಲೇಷಿಸಿ bearing faults, shaft misalignment, rotor unbalance, motor overload ಮತ್ತು overheating ಮುಂತಾದ ಅಸಾಮಾನ್ಯ ಸ್ಥಿತಿಗಳನ್ನು ಗುರುತಿಸಲು ಸಹಾಯ ಮಾಡುತ್ತದೆ.' },
    { q: 'Critical threshold ಮೀರಿದಾಗ ಏನಾಗುತ್ತದೆ?', a: 'Critical threshold ಕಂಡುಬಂದಾಗ ಸಂಪರ್ಕಿತ relay system ಮೂಲಕ IntelliWatch equipment stop command ನೀಡಬಹುದು. Dashboard ನಲ್ಲಿ alert ಕಾಣಿಸುತ್ತದೆ ಮತ್ತು event ದಾಖಲಾಗುತ್ತದೆ. ನಿಜವಾದ hardware stop IoT ಮತ್ತು relay integration ಮೇಲೆ ಅವಲಂಬಿತವಾಗಿದೆ.' },
    { q: 'Warning mode ಉಪಕರಣವನ್ನು ಹೇಗೆ ರಕ್ಷಿಸುತ್ತದೆ?', a: 'Warning mode readings ಸಾಮಾನ್ಯ ಮಿತಿಯಿಂದ ಹೊರಗೆ ಹೋಗುತ್ತಿರುವುದನ್ನು ಸೂಚಿಸುತ್ತದೆ. ನಿಯಂತ್ರಿತ speed reduction ಗೆ compatible motor controller ಮತ್ತು hardware integration ಅಗತ್ಯವಿದೆ.' },
    { q: 'ಕ್ರಮೇಣ ವೇಗ ಕಡಿಮೆ ಮಾಡುವುದು ಏಕೆ ಉಪಯುಕ್ತ?', a: 'ಯಂತ್ರದ ವೇಗವನ್ನು ಕ್ರಮೇಣ ಕಡಿಮೆ ಮಾಡುವುದರಿಂದ ಹಠಾತ್ mechanical stress ತಪ್ಪಿಸಲು ಸಹಾಯವಾಗುತ್ತದೆ. ಪರಿಶೀಲನೆಗೆ operators ಗೆ ಸಮಯ ಸಿಗುತ್ತದೆ.' },
    { q: 'IntelliWatch SCADA ಅಥವಾ PLC ಜೊತೆ ಸಂಪರ್ಕಿಸಬಹುದೇ?', a: 'IntelliWatch backend APIs ಮತ್ತು real-time communication ಸೌಲಭ್ಯಗಳನ್ನು ಒದಗಿಸುತ್ತದೆ. ನಿರ್ದಿಷ್ಟ SCADA ಅಥವಾ PLC integration compatible protocols ಮತ್ತು configuration ಮೇಲೆ ಅವಲಂಬಿತವಾಗಿದೆ.' },
    { q: 'IntelliWatch ಯಾವ sensors support ಮಾಡುತ್ತದೆ?', a: 'ಇದು ADXL345 vibration sensor, DS18B20 temperature sensor ಮತ್ತು ACS712 current sensor ಗಳೊಂದಿಗೆ ಕೆಲಸ ಮಾಡಲು ವಿನ್ಯಾಸಗೊಳಿಸಲಾಗಿದೆ. ADS1115 ADC current sensor output ಅನ್ನು digital ರೂಪಕ್ಕೆ ಪರಿವರ್ತಿಸಬಹುದು.' },
    { q: 'Anomaly detection ಎಷ್ಟು accurate?', a: 'Machine-learning model KAIST bearing fault dataset ನ features ಬಳಸುತ್ತದೆ. ನಿಜವಾದ performance sensor placement, machine type ಮತ್ತು data quality ಮೇಲೆ ಅವಲಂಬಿತವಾಗಿದೆ.' },
    { q: 'IoT hardware disconnect ಆದರೆ ಏನಾಗುತ್ತದೆ?', a: 'Sensor data ಲಭ್ಯವಿಲ್ಲದಿದ್ದರೆ IntelliWatch IoT signal ಗಾಗಿ ಕಾಯುತ್ತಿರುವುದನ್ನು ಸೂಚಿಸಬಹುದು. Hardware protection ನಿಜವಾದ relay configuration ಮತ್ತು safety ವ್ಯವಸ್ಥೆಗಳ ಮೇಲೆ ಅವಲಂಬಿತವಾಗಿದೆ.' },
    { q: 'User roles ಹೇಗೆ ಕಾರ್ಯನಿರ್ವಹಿಸುತ್ತವೆ?', a: 'ADMIN users ಮತ್ತು system settings ನಿರ್ವಹಿಸುತ್ತಾರೆ. OPERATOR operational information ಮತ್ತು alerts ನೋಡುತ್ತಾರೆ. MAINTENANCE ENGINEER maintenance ಮತ್ತು diagnostic features ಬಳಸುತ್ತಾರೆ.' },
    { q: 'IntelliWatch commercial monitoring platforms ಗಿಂತ ಹೇಗೆ ಭಿನ್ನವಾಗಿದೆ?', a: 'IntelliWatch ಕಡಿಮೆ ವೆಚ್ಚದ flexible monitoring ಮತ್ತು decision-support system ಆಗಿದೆ. Sensor monitoring, anomaly detection, alerts ಮತ್ತು equipment information ಅನ್ನು ಒಂದೇ platform ನಲ್ಲಿ ಒದಗಿಸುತ್ತದೆ.' },
    { q: 'TenderWatch Leaderboard ಎಂದರೇನು?', a: 'TenderWatch ಒಂದು leaderboard feature ಆಗಿದ್ದು industrial organizations ಮಾಹಿತಿ ಮತ್ತು predictive maintenance maturity scores ತೋರಿಸುತ್ತದೆ.' },
    { q: 'IntelliWatch ಒಂದೇ ಸಮಯದಲ್ಲಿ ಹಲವು machines monitor ಮಾಡಬಹುದೇ?', a: 'ಪ್ರಸ್ತುತ setup ಒಂದು machine monitoring node ಗಾಗಿ ವಿನ್ಯಾಸಗೊಳಿಸಲಾಗಿದೆ. ಹಲವು machines monitor ಮಾಡಲು ಹೆಚ್ಚುವರಿ hardware nodes ಮತ್ತು configuration ಅಗತ್ಯವಿದೆ.' },
    { q: 'Equipment Vision ಎಂದರೇನು?', a: 'Equipment Vision live camera ಅಥವಾ upload ಮಾಡಿದ photograph ಬಳಸಿ equipment ಗುರುತಿಸಲು ಸಹಾಯ ಮಾಡುತ್ತದೆ.' },
    { q: 'ನಾನು equipment photograph upload ಮಾಡಬಹುದೇ?', a: 'ಹೌದು. Equipment image upload ಮಾಡಿ ಅದರ visual identification ಮತ್ತು ಮಾಹಿತಿಯನ್ನು ಪಡೆಯಬಹುದು.' },
    { q: 'Equipment Vision live camera ಬಳಸಬಹುದೇ?', a: 'ಹೌದು. Live camera ಮೂಲಕ ಸೆರೆಹಿಡಿದ images ವಿಶ್ಲೇಷಿಸಿ ಕಾಣುವ equipment ಗುರುತಿಸಬಹುದು.' },
    { q: 'Equipment Vision equipment damage ಗುರುತಿಸಬಹುದೇ?', a: 'Image ನಲ್ಲಿ ಸ್ಪಷ್ಟವಾಗಿ ಕಾಣುವ damage, corrosion ಅಥವಾ loose connections ಮುಂತಾದ ಲಕ್ಷಣಗಳನ್ನು highlight ಮಾಡಲು ಸಹಾಯ ಮಾಡುತ್ತದೆ. ಇದು ತಜ್ಞರ ನೇರ ಪರಿಶೀಲನೆಗೆ ಪರ್ಯಾಯವಲ್ಲ.' },
    { q: 'Laboratory Equipment feature ಎಂದರೇನು?', a: 'ಸಾಮಾನ್ಯ industrial ಮತ್ತು laboratory equipment, ಅವುಗಳ ಉದ್ದೇಶ, ಕಾರ್ಯವಿಧಾನ ಮತ್ತು ಬಳಕೆಗಳ ಬಗ್ಗೆ ಮಾಹಿತಿ ನೀಡುತ್ತದೆ.' },
    { q: 'IntelliWatch ಹಲವು ಭಾಷೆಗಳನ್ನು support ಮಾಡುತ್ತದೆಯೇ?', a: 'ಹೌದು. Interface English, Hindi, Kannada, Tamil ಮತ್ತು Telugu ಭಾಷೆಗಳನ್ನು support ಮಾಡುತ್ತದೆ.' },
  ],

  ta: [
    { q: 'IntelliWatch என்ன கோளாறுகளை கண்டறிய முடியும்?', a: 'அதிர்வு, வெப்பநிலை மற்றும் மின்னோட்ட அளவீடுகளை ஆய்வு செய்து bearing faults, shaft misalignment, rotor unbalance, motor overload மற்றும் overheating போன்ற அசாதாரண நிலைகளை அடையாளம் காண உதவுகிறது.' },
    { q: 'Critical threshold மீறும்போது என்ன நடக்கும்?', a: 'Critical threshold கண்டறியப்பட்டால் இணைக்கப்பட்ட relay system மூலம் IntelliWatch equipment stop command வழங்க முடியும். Dashboard இல் alert காட்டப்படும். உண்மையான hardware stop என்பது IoT மற்றும் relay integration ஐப் பொறுத்தது.' },
    { q: 'Warning mode உபகரணத்தை எவ்வாறு பாதுகாக்கிறது?', a: 'Warning mode அளவீடுகள் சாதாரண வரம்பை மீறுவதைச் சுட்டிக்காட்டுகிறது. கட்டுப்படுத்தப்பட்ட speed reduction க்கு compatible motor controller மற்றும் hardware integration தேவை.' },
    { q: 'படிப்படியாக வேகத்தைக் குறைப்பது ஏன் பயனுள்ளது?', a: 'இயந்திர வேகத்தைப் படிப்படியாகக் குறைப்பது திடீர் mechanical stress ஐத் தவிர்க்க உதவும். ஆய்வு செய்ய operators க்கு நேரமும் கிடைக்கும்.' },
    { q: 'IntelliWatch SCADA அல்லது PLC உடன் இணைக்க முடியுமா?', a: 'IntelliWatch backend APIs மற்றும் real-time communication வசதிகளை வழங்குகிறது. குறிப்பிட்ட SCADA அல்லது PLC integration compatible protocols மற்றும் configuration ஐப் பொறுத்தது.' },
    { q: 'IntelliWatch எந்த sensors ஐ support செய்கிறது?', a: 'ADXL345 vibration sensor, DS18B20 temperature sensor மற்றும் ACS712 current sensor ஆகியவற்றுடன் வேலை செய்யும் வகையில் வடிவமைக்கப்பட்டுள்ளது. ADS1115 ADC current sensor output ஐ digital ஆக மாற்றலாம்.' },
    { q: 'Anomaly detection எவ்வளவு துல்லியமானது?', a: 'Machine-learning model KAIST bearing fault dataset features ஐப் பயன்படுத்துகிறது. உண்மையான செயல்திறன் sensor placement, machine type மற்றும் data quality ஐப் பொறுத்தது.' },
    { q: 'IoT hardware disconnect ஆனால் என்ன நடக்கும்?', a: 'Sensor data கிடைக்காவிட்டால் IntelliWatch IoT signal க்காக காத்திருப்பதைக் காட்டலாம். Hardware protection என்பது உண்மையான relay configuration மற்றும் safety அமைப்புகளைப் பொறுத்தது.' },
    { q: 'User roles எவ்வாறு செயல்படுகின்றன?', a: 'ADMIN users மற்றும் system settings ஐ நிர்வகிக்கிறார். OPERATOR operational information மற்றும் alerts ஐப் பார்க்கிறார். MAINTENANCE ENGINEER maintenance மற்றும் diagnostic features ஐப் பயன்படுத்துகிறார்.' },
    { q: 'Commercial monitoring platforms இலிருந்து IntelliWatch எவ்வாறு வேறுபடுகிறது?', a: 'IntelliWatch குறைந்த செலவிலான flexible monitoring மற்றும் decision-support system ஆக வடிவமைக்கப்பட்டுள்ளது. Sensor monitoring, anomaly detection, alerts மற்றும் equipment information ஆகியவற்றை ஒரே platform இல் வழங்குகிறது.' },
    { q: 'TenderWatch Leaderboard என்றால் என்ன?', a: 'TenderWatch என்பது industrial organizations பற்றிய தகவல்களையும் predictive maintenance maturity scores ஐயும் காட்டும் leaderboard feature ஆகும்.' },
    { q: 'IntelliWatch பல machines ஐ ஒரே நேரத்தில் கண்காணிக்குமா?', a: 'தற்போதைய setup ஒரு machine monitoring node க்காக வடிவமைக்கப்பட்டுள்ளது. பல machines கண்காணிக்க கூடுதல் hardware nodes மற்றும் configuration தேவை.' },
    { q: 'Equipment Vision என்றால் என்ன?', a: 'Equipment Vision live camera அல்லது upload செய்யப்பட்ட photograph மூலம் equipment ஐ அடையாளம் காண உதவுகிறது.' },
    { q: 'Equipment photograph ஐ upload செய்ய முடியுமா?', a: 'ஆம். Equipment image ஐ upload செய்து அதன் visual identification மற்றும் தகவல்களைப் பெறலாம்.' },
    { q: 'Equipment Vision live camera ஐப் பயன்படுத்துமா?', a: 'ஆம். Live camera மூலம் எடுக்கப்படும் images ஐ ஆய்வு செய்து காணப்படும் equipment ஐ அடையாளம் காண முடியும்.' },
    { q: 'Equipment Vision equipment damage ஐக் கண்டறியுமா?', a: 'Image இல் தெளிவாகத் தெரியும் damage, corrosion அல்லது loose connections போன்ற அறிகுறிகளை highlight செய்ய உதவும். இது தகுதியான நபரின் நேரடி ஆய்வுக்கு மாற்றாகாது.' },
    { q: 'Laboratory Equipment feature என்றால் என்ன?', a: 'பொதுவான industrial மற்றும் laboratory equipment, அவற்றின் நோக்கம், செயல்முறை மற்றும் பயன்பாடுகள் பற்றிய தகவல்களை வழங்குகிறது.' },
    { q: 'IntelliWatch பல மொழிகளை support செய்கிறதா?', a: 'ஆம். Interface English, Hindi, Kannada, Tamil மற்றும் Telugu மொழிகளை support செய்கிறது.' },
  ],

  te: [
    { q: 'IntelliWatch ఏ లోపాలను గుర్తించగలదు?', a: 'కంపనం, ఉష్ణోగ్రత మరియు కరెంట్ రీడింగ్‌లను విశ్లేషించి bearing faults, shaft misalignment, rotor unbalance, motor overload మరియు overheating వంటి అసాధారణ పరిస్థితులను గుర్తించడంలో సహాయపడుతుంది.' },
    { q: 'Critical threshold దాటినప్పుడు ఏమి జరుగుతుంది?', a: 'Critical threshold గుర్తించినప్పుడు కనెక్ట్ చేసిన relay system ద్వారా IntelliWatch equipment stop command ఇవ్వగలదు. Dashboard లో alert కనిపిస్తుంది. నిజమైన hardware stop IoT మరియు relay integration పై ఆధారపడి ఉంటుంది.' },
    { q: 'Warning mode పరికరాన్ని ఎలా రక్షిస్తుంది?', a: 'Warning mode రీడింగ్‌లు సాధారణ పరిమితులను దాటుతున్నాయని సూచిస్తుంది. నియంత్రిత speed reduction కోసం compatible motor controller మరియు hardware integration అవసరం.' },
    { q: 'క్రమంగా వేగం తగ్గించడం ఎందుకు ఉపయోగకరం?', a: 'యంత్రం వేగాన్ని క్రమంగా తగ్గించడం వల్ల ఆకస్మిక mechanical stress తగ్గుతుంది. Operators కు పరికరాన్ని పరిశీలించడానికి సమయం లభిస్తుంది.' },
    { q: 'IntelliWatch SCADA లేదా PLC తో అనుసంధానం చేయవచ్చా?', a: 'IntelliWatch backend APIs మరియు real-time communication సదుపాయాలను అందిస్తుంది. నిర్దిష్ట SCADA లేదా PLC integration compatible protocols మరియు configuration పై ఆధారపడి ఉంటుంది.' },
    { q: 'IntelliWatch ఏ sensors ను support చేస్తుంది?', a: 'ఇది ADXL345 vibration sensor, DS18B20 temperature sensor మరియు ACS712 current sensor లతో పనిచేసేలా రూపొందించబడింది. ADS1115 ADC current sensor output ను digital రూపంలోకి మార్చగలదు.' },
    { q: 'Anomaly detection ఎంత ఖచ్చితమైనది?', a: 'Machine-learning model KAIST bearing fault dataset features ను ఉపయోగిస్తుంది. నిజమైన పనితీరు sensor placement, machine type మరియు data quality పై ఆధారపడి ఉంటుంది.' },
    { q: 'IoT hardware disconnect అయితే ఏమి జరుగుతుంది?', a: 'Sensor data అందుబాటులో లేకపోతే IntelliWatch IoT signal కోసం వేచి ఉన్నట్లు చూపగలదు. Hardware protection నిజమైన relay configuration మరియు safety ఏర్పాట్లపై ఆధారపడి ఉంటుంది.' },
    { q: 'User roles ఎలా పనిచేస్తాయి?', a: 'ADMIN users మరియు system settings ను నిర్వహిస్తారు. OPERATOR operational information మరియు alerts ను చూస్తారు. MAINTENANCE ENGINEER maintenance మరియు diagnostic features ను ఉపయోగిస్తారు.' },
    { q: 'Commercial monitoring platforms తో పోలిస్తే IntelliWatch ఎలా భిన్నంగా ఉంటుంది?', a: 'IntelliWatch తక్కువ ఖర్చుతో కూడిన flexible monitoring మరియు decision-support system. Sensor monitoring, anomaly detection, alerts మరియు equipment information ను ఒకే platform లో అందిస్తుంది.' },
    { q: 'TenderWatch Leaderboard అంటే ఏమిటి?', a: 'TenderWatch అనేది industrial organizations సమాచారం మరియు predictive maintenance maturity scores ను చూపించే leaderboard feature.' },
    { q: 'IntelliWatch ఒకేసారి అనేక machines ను monitor చేయగలదా?', a: 'ప్రస్తుత setup ఒక machine monitoring node కోసం రూపొందించబడింది. అనేక machines ను monitor చేయడానికి అదనపు hardware nodes మరియు configuration అవసరం.' },
    { q: 'Equipment Vision అంటే ఏమిటి?', a: 'Equipment Vision live camera లేదా upload చేసిన photograph ద్వారా equipment ను గుర్తించడంలో సహాయపడుతుంది.' },
    { q: 'Equipment photograph ను upload చేయవచ్చా?', a: 'అవును. Equipment image ను upload చేసి దాని visual identification మరియు సమాచారాన్ని పొందవచ్చు.' },
    { q: 'Equipment Vision live camera ను ఉపయోగించగలదా?', a: 'అవును. Live camera ద్వారా తీసిన images ను విశ్లేషించి కనిపించే equipment ను గుర్తించగలదు.' },
    { q: 'Equipment Vision పరికరాల damage ను గుర్తించగలదా?', a: 'Image లో స్పష్టంగా కనిపించే damage, corrosion లేదా loose connections వంటి లక్షణాలను highlight చేయడంలో సహాయపడుతుంది. ఇది నిపుణుల ప్రత్యక్ష తనిఖీకి ప్రత్యామ్నాయం కాదు.' },
    { q: 'Laboratory Equipment feature అంటే ఏమిటి?', a: 'సాధారణ industrial మరియు laboratory equipment, వాటి ఉద్దేశ్యం, పని చేసే విధానం మరియు ఉపయోగాల గురించి సమాచారాన్ని అందిస్తుంది.' },
    { q: 'IntelliWatch అనేక భాషలను support చేస్తుందా?', a: 'అవును. Interface English, Hindi, Kannada, Tamil మరియు Telugu భాషలను support చేస్తుంది.' },
  ],
}

const SENSOR_TABLE = [
  {
    name: 'ADXL345',
    type: 'Vibration Sensor',
    purpose: 'Measures machine vibration and movement.',
  },
  {
    name: 'DS18B20',
    type: 'Temperature Sensor',
    purpose: 'Measures equipment temperature.',
  },
  {
    name: 'ACS712',
    type: 'Current Sensor',
    purpose: 'Measures electrical current.',
  },
  {
    name: 'ADS1115',
    type: 'Analog-to-Digital Converter',
    purpose: 'Converts analog sensor output into digital readings.',
  },
]

const TECH_STACK = [
  { name: 'React', category: 'Frontend' },
  { name: 'Vite', category: 'Frontend tooling' },
  { name: 'FastAPI', category: 'Backend API' },
  { name: 'Python', category: 'Backend and ML' },
  { name: 'SQLite', category: 'Database' },
  { name: 'Machine Learning', category: 'Anomaly detection' },
  { name: 'WebSockets', category: 'Real-time communication' },
  { name: 'JWT', category: 'Authentication' },
]

const FEEDBACK_STRINGS = {
  en: {
    name: 'Your Name',
    email: 'Email Address',
    message: 'Your Feedback',
    placeholder: 'Share your suggestions or report an issue...',
    submit: 'Submit Feedback',
    sending: 'Submitting...',
    success: 'Thank you! Your feedback has been submitted.',
    error: 'Unable to submit feedback. Please try again.',
  },
  hi: {
    name: 'आपका नाम',
    email: 'ईमेल पता',
    message: 'आपकी प्रतिक्रिया',
    placeholder: 'अपने सुझाव साझा करें या समस्या बताएँ...',
    submit: 'प्रतिक्रिया भेजें',
    sending: 'भेजा जा रहा है...',
    success: 'धन्यवाद! आपकी प्रतिक्रिया भेज दी गई है।',
    error: 'प्रतिक्रिया भेजने में समस्या हुई। फिर से प्रयास करें।',
  },
  kn: {
    name: 'ನಿಮ್ಮ ಹೆಸರು',
    email: 'ಇಮೇಲ್ ವಿಳಾಸ',
    message: 'ನಿಮ್ಮ ಅಭಿಪ್ರಾಯ',
    placeholder: 'ನಿಮ್ಮ ಸಲಹೆಗಳನ್ನು ಹಂಚಿಕೊಳ್ಳಿ ಅಥವಾ ಸಮಸ್ಯೆಯನ್ನು ತಿಳಿಸಿ...',
    submit: 'ಅಭಿಪ್ರಾಯ ಸಲ್ಲಿಸಿ',
    sending: 'ಸಲ್ಲಿಸಲಾಗುತ್ತಿದೆ...',
    success: 'ಧನ್ಯವಾದಗಳು! ನಿಮ್ಮ ಅಭಿಪ್ರಾಯ ಸಲ್ಲಿಸಲಾಗಿದೆ.',
    error: 'ಅಭಿಪ್ರಾಯ ಸಲ್ಲಿಸಲು ಸಾಧ್ಯವಾಗಲಿಲ್ಲ. ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.',
  },
  ta: {
    name: 'உங்கள் பெயர்',
    email: 'மின்னஞ்சல் முகவரி',
    message: 'உங்கள் கருத்து',
    placeholder: 'உங்கள் ஆலோசனைகளைப் பகிரவும் அல்லது சிக்கலைத் தெரிவிக்கவும்...',
    submit: 'கருத்தைச் சமர்ப்பிக்கவும்',
    sending: 'சமர்ப்பிக்கப்படுகிறது...',
    success: 'நன்றி! உங்கள் கருத்து சமர்ப்பிக்கப்பட்டது.',
    error: 'கருத்தைச் சமர்ப்பிக்க முடியவில்லை. மீண்டும் முயற்சிக்கவும்.',
  },
  te: {
    name: 'మీ పేరు',
    email: 'ఇమెయిల్ చిరునామా',
    message: 'మీ అభిప్రాయం',
    placeholder: 'మీ సూచనలను పంచుకోండి లేదా సమస్యను తెలియజేయండి...',
    submit: 'అభిప్రాయాన్ని సమర్పించండి',
    sending: 'సమర్పిస్తోంది...',
    success: 'ధన్యవాదాలు! మీ అభిప్రాయం సమర్పించబడింది.',
    error: 'అభిప్రాయాన్ని సమర్పించలేకపోయాము. మళ్లీ ప్రయత్నించండి.',
  },
}

function FAQItem({ item, index }) {
  const [open, setOpen] = useState(false)

  return (
    <div className="faq-item">
      <button
        type="button"
        className={`faq-question ${open ? 'active' : ''}`}
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-controls={`faq-answer-${index}`}
      >
        <span>{item.q}</span>
        <span className="faq-icon">{open ? '−' : '+'}</span>
      </button>

      {open && (
        <div className="faq-answer" id={`faq-answer-${index}`}>
          {item.a}
        </div>
      )}
    </div>
  )
}

function FeedbackSection({ lang }) {
  const strings = FEEDBACK_STRINGS[lang] || FEEDBACK_STRINGS.en
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [message, setMessage] = useState('')
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (event) => {
    event.preventDefault()
    setStatus('')
    setLoading(true)

    try {
      const API = (import.meta.env.VITE_API_URL || 'http://localhost:8000')
        .replace(/\/+$/, '')

      const response = await fetch(`${API}/feedback`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name,
          email,
          message,
        }),
      })

      if (!response.ok) {
        throw new Error('Feedback submission failed')
      }

      setStatus('success')
      setName('')
      setEmail('')
      setMessage('')
    } catch {
      setStatus('error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="about-section feedback-section">
      <h2>{CONTENT[lang]?.feedback || CONTENT.en.feedback}</h2>

      <form onSubmit={handleSubmit} className="feedback-form">
        <label>
          {strings.name}
          <input
            type="text"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder={strings.name}
            required
          />
        </label>

        <label>
          {strings.email}
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder={strings.email}
            required
          />
        </label>

        <label>
          {strings.message}
          <textarea
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder={strings.placeholder}
            rows={4}
            required
          />
        </label>

        <button type="submit" disabled={loading}>
          {loading ? strings.sending : strings.submit}
        </button>

        {status === 'success' && (
          <p className="feedback-success">{strings.success}</p>
        )}

        {status === 'error' && (
          <p className="feedback-error">{strings.error}</p>
        )}
      </form>
    </section>
  )
}

function AboutPage() {
  const lang = useLang()
  const language = CONTENT[lang] ? lang : 'en'
  const content = CONTENT[language]
  const objectives = OBJECTIVES[language] || OBJECTIVES.en
  const faqs = FAQ[language] || FAQ.en

  return (
    <main className="about-page">
      <section className="about-hero">
        <h1>{content.title}</h1>
        <p>{content.subtitle}</p>
      </section>

      <section className="about-section">
        <h2>{content.objectives}</h2>
        <div className="objectives-grid">
          {objectives.map((objective, index) => (
            <div className="objective-card" key={index}>
              <span className="objective-number">{index + 1}</span>
              <p>{objective}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="about-section">
        <h2>{content.protection}</h2>
        <div className="protection-grid">
          <article className="protection-card">
            <h3>Normal</h3>
            <p>
              Equipment readings are within the configured operating limits.
              The system continues monitoring and analysing sensor data.
            </p>
          </article>

          <article className="protection-card">
            <h3>Warning</h3>
            <p>
              Readings have moved beyond normal limits. The system displays
              a warning so that operators can inspect the equipment.
              Controlled speed reduction requires compatible hardware.
            </p>
          </article>

          <article className="protection-card">
            <h3>Critical</h3>
            <p>
              A critical condition triggers an alert and can issue a stop
              command through an integrated relay system. Actual stopping
              depends on hardware integration.
            </p>
          </article>
        </div>
      </section>

      <section className="about-section">
        <h2>{content.sensors}</h2>
        <div className="sensor-table-wrapper">
          <table className="sensor-table">
            <thead>
              <tr>
                <th>Component</th>
                <th>Type</th>
                <th>Purpose</th>
              </tr>
            </thead>
            <tbody>
              {SENSOR_TABLE.map((sensor) => (
                <tr key={sensor.name}>
                  <td>{sensor.name}</td>
                  <td>{sensor.type}</td>
                  <td>{sensor.purpose}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="about-section">
        <h2>{content.tech}</h2>
        <div className="tech-stack-grid">
          {TECH_STACK.map((technology) => (
            <div className="tech-card" key={technology.name}>
              <h3>{technology.name}</h3>
              <p>{technology.category}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="about-section">
        <h2>{content.faq}</h2>
        <div className="faq-list">
          {faqs.map((item, index) => (
            <FAQItem
              key={`${language}-${index}`}
              item={item}
              index={`${language}-${index}`}
            />
          ))}
        </div>
      </section>

      <FeedbackSection lang={language} />
    </main>
  )
}

export default AboutPage