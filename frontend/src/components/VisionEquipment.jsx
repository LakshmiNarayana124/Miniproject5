
import { useEffect, useRef, useState } from "react";
import useLang from "../useLang";

const API_BASE = (
  import.meta.env.VITE_API_URL || "http://localhost:8000"
).replace(/\/+$/, "");

const MAX_IMAGE_SIZE = 8 * 1024 * 1024;
const MAX_FRAME_WIDTH = 640;
const DETECTION_INTERVAL = 500;
const ANALYSIS_TIMEOUT = 90000;
const TRACK_IOU_THRESHOLD = 0.3;
const MAX_MISSED_FRAMES = 3;

const SUPPORTED_TYPES = [
  "image/jpeg",
  "image/png",
  "image/webp",
];

const VISION_TEXT = {
  en: {
    eyebrow: "IntelliWatch · AI-assisted inspection",
    title: "Equipment Vision",
    description:
      "Capture or upload an equipment photograph to identify the equipment, understand its working principle and explore possible monitoring applications using IntelliWatch sensors.",
    image: "Equipment image",
    cameraActive: "Camera active",
    cameraInactive: "Camera inactive",
    noImage: "No equipment image selected",
    noImageDescription:
      "Open the camera to capture an image, or upload an existing equipment photograph.",
    openCamera: "Open camera",
    captureImage: "Capture image",
    startDetection: "Start live detection",
    stopDetection: "Stop live detection",
    emergencyStop: "Emergency stop camera",
    uploadImage: "Upload image",
    analyse: "Analyse equipment",
    analysing: "Analysing...",
    cancel: "Cancel analysis",
    clear: "Clear image",
    inactive: "Inactive",
    starting: "Starting...",
    retrying: "Retrying...",
    detected: "object(s) detected",
    visibleObjects: "visible object(s)",
    liveDetection: "Live detection:",
    cameraOpened: "Camera opened successfully.",
    cameraStopped: "Camera stopped and released.",
    imageCaptured: "Image captured successfully.",
    cancelled: "Equipment analysis was cancelled.",
    timeout:
      "Equipment analysis timed out after 90 seconds. The service may be busy. Please try again.",
    cameraUnavailable:
      "Camera access requires HTTPS or localhost and a supported browser.",
    cameraDenied:
      "Camera permission was denied. Allow camera access in your browser settings.",
    cameraNotFound: "No camera was found on this device.",
    cameraFailed: "Unable to open the camera. Please try again.",
    cameraNotReady:
      "The camera is not ready. Please wait and try again.",
    captureFailed: "Image capture failed. Please try again.",
    prepareCapture: "Unable to prepare the captured image.",
    prepareFrame: "Unable to prepare camera frame.",
    encodeFrame: "Unable to encode camera frame.",
    sessionExpired: "Your session has expired. Please log in again.",
    unauthorizedDetection:
      "You are not authorised to use live Equipment Vision. Please sign in again or contact your administrator.",
    unauthorizedAnalysis:
      "You are not authorised to use Equipment Vision. Please sign in again or contact your administrator.",
    detectionFailed: "Live object detection failed.",
    incompleteDetection:
      "The detection service returned an incomplete response.",
    detectionError: "Live detection encountered an error.",
    selectImage: "Please select a JPEG, PNG or WEBP image.",
    imageTooLarge: "The image must be smaller than 8 MB.",
    capturedTooLarge:
      "Captured image exceeds the 8 MB size limit.",
    selectFirst: "Capture or upload an equipment image first.",
    invalidResponse:
      "The server returned an unreadable response. Please try again.",
    analysisFailed: "Equipment image analysis failed.",
    incompleteAnalysis:
      "The server returned an incomplete analysis.",
    invalidAnalysis:
      "The server returned an invalid analysis format.",
    resultError:
      "Unable to analyse the equipment image. Please try again.",
    analysisResult: "Analysis result",
    confidence: "Confidence",
    purpose: "Purpose",
    working: "Working principle",
    relevance: "IntelliWatch relevance",
    sensors: "Sensor compatibility",
    anomalies: "Possible anomalies",
    limitations: "Limitations",
    equipmentNotIdentified: "Equipment not identified",
    confidenceNotSpecified: "Not specified",
    verifyIdentity:
      "AI-generated visual identification. Verify the equipment identity against its physical label or technical documentation.",
    noAnomalies: "No possible anomalies were listed.",
    noLimitations: "No additional limitations were listed.",
    disclaimer:
      "This is an AI-assisted visual assessment, not a certified engineering inspection. A photograph cannot establish internal condition, electrical safety, actual sensor installation or equipment operating limits. Do not use this result as the sole basis for maintenance or safety decisions.",
    liveNote:
      "Live detection sends sampled camera frames to the backend while enabled. Frames are processed in memory and are not persistently recorded or saved. Gemini analysis is performed separately on the selected still image. Supported formats: JPEG, PNG and WEBP. Maximum image size: 8 MB.",
    detectionNote:
      "Detection uses a general-purpose COCO object model. It can recognise supported everyday object categories, but may not identify specialised industrial machinery, internal faults or machine-specific components. Detection results are not certified equipment inspections.",
    purposeUnavailable: "Purpose information is unavailable.",
    workingUnavailable:
      "Working principle information is unavailable.",
    relevanceUnavailable:
      "IntelliWatch relevance information is unavailable.",
  },

  hi: {
    eyebrow: "IntelliWatch · AI-सहायता प्राप्त निरीक्षण",
    title: "उपकरण दृश्य पहचान",
    description:
      "उपकरण की तस्वीर लें या अपलोड करें। उपकरण की पहचान करें, उसके काम करने का तरीका समझें और IntelliWatch सेंसर से उसकी निगरानी की संभावनाएँ जानें।",
    image: "उपकरण की तस्वीर",
    cameraActive: "कैमरा चालू है",
    cameraInactive: "कैमरा बंद है",
    noImage: "कोई उपकरण तस्वीर चुनी नहीं गई",
    noImageDescription:
      "तस्वीर लेने के लिए कैमरा खोलें या पहले से मौजूद उपकरण की तस्वीर अपलोड करें।",
    openCamera: "कैमरा खोलें",
    captureImage: "तस्वीर लें",
    startDetection: "लाइव पहचान शुरू करें",
    stopDetection: "लाइव पहचान रोकें",
    emergencyStop: "कैमरा तुरंत बंद करें",
    uploadImage: "तस्वीर अपलोड करें",
    analyse: "उपकरण का विश्लेषण करें",
    analysing: "विश्लेषण हो रहा है...",
    cancel: "विश्लेषण रद्द करें",
    clear: "तस्वीर हटाएँ",
    inactive: "निष्क्रिय",
    starting: "शुरू हो रहा है...",
    retrying: "दोबारा प्रयास हो रहा है...",
    detected: "वस्तु(एँ) पहचानी गईं",
    visibleObjects: "दिखाई देने वाली वस्तु(एँ)",
    liveDetection: "लाइव पहचान:",
    cameraOpened: "कैमरा सफलतापूर्वक खुल गया।",
    cameraStopped: "कैमरा बंद कर दिया गया है।",
    imageCaptured: "तस्वीर सफलतापूर्वक ली गई।",
    cancelled: "उपकरण का विश्लेषण रद्द कर दिया गया।",
    timeout:
      "90 सेकंड बाद उपकरण विश्लेषण का समय समाप्त हो गया। सेवा व्यस्त हो सकती है। कृपया दोबारा प्रयास करें।",
    cameraUnavailable:
      "कैमरे के उपयोग के लिए HTTPS या localhost और समर्थित ब्राउज़र आवश्यक है।",
    cameraDenied:
      "कैमरे की अनुमति नहीं मिली। ब्राउज़र सेटिंग में कैमरे की अनुमति दें।",
    cameraNotFound: "इस डिवाइस पर कोई कैमरा नहीं मिला।",
    cameraFailed: "कैमरा नहीं खुल सका। कृपया दोबारा प्रयास करें।",
    cameraNotReady:
      "कैमरा अभी तैयार नहीं है। कृपया प्रतीक्षा करें और फिर प्रयास करें।",
    captureFailed: "तस्वीर नहीं ली जा सकी। कृपया दोबारा प्रयास करें।",
    prepareCapture: "तस्वीर तैयार नहीं की जा सकी।",
    prepareFrame: "कैमरा फ्रेम तैयार नहीं किया जा सका।",
    encodeFrame: "कैमरा फ्रेम तैयार नहीं किया जा सका।",
    sessionExpired: "आपका सत्र समाप्त हो गया है। कृपया फिर से लॉग इन करें।",
    unauthorizedDetection:
      "आपको लाइव उपकरण पहचान की अनुमति नहीं है। कृपया फिर से लॉग इन करें या व्यवस्थापक से संपर्क करें।",
    unauthorizedAnalysis:
      "आपको उपकरण विश्लेषण की अनुमति नहीं है। कृपया फिर से लॉग इन करें या व्यवस्थापक से संपर्क करें।",
    detectionFailed: "लाइव वस्तु पहचान विफल रही।",
    incompleteDetection:
      "पहचान सेवा से अधूरा परिणाम प्राप्त हुआ।",
    detectionError: "लाइव पहचान में त्रुटि हुई।",
    selectImage: "कृपया JPEG, PNG या WEBP तस्वीर चुनें।",
    imageTooLarge: "तस्वीर का आकार 8 MB से कम होना चाहिए।",
    capturedTooLarge:
      "ली गई तस्वीर का आकार 8 MB की सीमा से अधिक है।",
    selectFirst: "पहले उपकरण की तस्वीर लें या अपलोड करें।",
    invalidResponse:
      "सर्वर से पढ़ने योग्य उत्तर नहीं मिला। कृपया दोबारा प्रयास करें।",
    analysisFailed: "उपकरण की तस्वीर का विश्लेषण विफल रहा।",
    incompleteAnalysis: "सर्वर से अधूरा विश्लेषण प्राप्त हुआ।",
    invalidAnalysis: "सर्वर से गलत विश्लेषण प्रारूप प्राप्त हुआ।",
    resultError:
      "उपकरण की तस्वीर का विश्लेषण नहीं हो सका। कृपया दोबारा प्रयास करें।",
    analysisResult: "विश्लेषण का परिणाम",
    confidence: "विश्वास स्तर",
    purpose: "उपयोग",
    working: "कार्य करने का सिद्धांत",
    relevance: "IntelliWatch में उपयोगिता",
    sensors: "सेंसर अनुकूलता",
    anomalies: "संभावित असामान्यताएँ",
    limitations: "सीमाएँ",
    equipmentNotIdentified: "उपकरण की पहचान नहीं हुई",
    confidenceNotSpecified: "निर्दिष्ट नहीं",
    verifyIdentity:
      "यह AI द्वारा किया गया दृश्य विश्लेषण है। उपकरण की पहचान उसके लेबल या तकनीकी दस्तावेज़ से सत्यापित करें।",
    noAnomalies: "कोई संभावित असामान्यता सूचीबद्ध नहीं है।",
    noLimitations: "कोई अतिरिक्त सीमा सूचीबद्ध नहीं है।",
    disclaimer:
      "यह AI-सहायता प्राप्त दृश्य मूल्यांकन है, प्रमाणित इंजीनियरिंग निरीक्षण नहीं। केवल तस्वीर से आंतरिक स्थिति, विद्युत सुरक्षा, सेंसर की वास्तविक स्थापना या उपकरण की संचालन सीमाएँ सुनिश्चित नहीं की जा सकतीं। रखरखाव या सुरक्षा निर्णय केवल इस परिणाम के आधार पर न लें।",
    liveNote:
      "लाइव पहचान चालू रहने पर कैमरे के चुने हुए फ्रेम सर्वर को भेजे जाते हैं। फ्रेम केवल मेमोरी में संसाधित होते हैं और स्थायी रूप से रिकॉर्ड या सेव नहीं किए जाते। Gemini विश्लेषण चुनी गई तस्वीर पर अलग से किया जाता है। समर्थित प्रारूप: JPEG, PNG और WEBP। अधिकतम आकार: 8 MB।",
    detectionNote:
      "पहचान के लिए सामान्य COCO ऑब्जेक्ट मॉडल का उपयोग किया जाता है। यह समर्थित सामान्य वस्तुओं को पहचान सकता है, लेकिन विशेष औद्योगिक मशीनों, आंतरिक खराबियों या मशीन के विशिष्ट भागों की पहचान नहीं कर सकता। यह प्रमाणित उपकरण निरीक्षण नहीं है।",
    purposeUnavailable: "उपयोग की जानकारी उपलब्ध नहीं है।",
    workingUnavailable:
      "कार्य सिद्धांत की जानकारी उपलब्ध नहीं है।",
    relevanceUnavailable:
      "IntelliWatch में उपयोगिता की जानकारी उपलब्ध नहीं है।",
  },

  kn: {
    eyebrow: "IntelliWatch · AI ನೆರವಿನ ಪರಿಶೀಲನೆ",
    title: "ಉಪಕರಣ ದೃಶ್ಯ ಗುರುತಿಸುವಿಕೆ",
    description:
      "ಉಪಕರಣದ ಫೋಟೋ ತೆಗೆದುಕೊಳ್ಳಿ ಅಥವಾ ಅಪ್‌ಲೋಡ್ ಮಾಡಿ. ಉಪಕರಣವನ್ನು ಗುರುತಿಸಿ, ಅದರ ಕಾರ್ಯವಿಧಾನವನ್ನು ಅರ್ಥಮಾಡಿಕೊಳ್ಳಿ ಮತ್ತು IntelliWatch ಸೆನ್ಸರ್‌ಗಳ ಮೂಲಕ ಮೇಲ್ವಿಚಾರಣೆಯ ಸಾಧ್ಯತೆಗಳನ್ನು ತಿಳಿಯಿರಿ.",
    image: "ಉಪಕರಣದ ಚಿತ್ರ",
    cameraActive: "ಕ್ಯಾಮೆರಾ ಸಕ್ರಿಯವಾಗಿದೆ",
    cameraInactive: "ಕ್ಯಾಮೆರಾ ನಿಷ್ಕ್ರಿಯವಾಗಿದೆ",
    noImage: "ಯಾವುದೇ ಉಪಕರಣದ ಚಿತ್ರವನ್ನು ಆಯ್ಕೆ ಮಾಡಿಲ್ಲ",
    noImageDescription:
      "ಚಿತ್ರ ತೆಗೆಯಲು ಕ್ಯಾಮೆರಾ ತೆರೆಯಿರಿ ಅಥವಾ ಈಗಾಗಲೇ ಇರುವ ಉಪಕರಣದ ಚಿತ್ರವನ್ನು ಅಪ್‌ಲೋಡ್ ಮಾಡಿ.",
    openCamera: "ಕ್ಯಾಮೆರಾ ತೆರೆಯಿರಿ",
    captureImage: "ಚಿತ್ರ ತೆಗೆಯಿರಿ",
    startDetection: "ಲೈವ್ ಗುರುತಿಸುವಿಕೆ ಪ್ರಾರಂಭಿಸಿ",
    stopDetection: "ಲೈವ್ ಗುರುತಿಸುವಿಕೆ ನಿಲ್ಲಿಸಿ",
    emergencyStop: "ಕ್ಯಾಮೆರಾವನ್ನು ತಕ್ಷಣ ನಿಲ್ಲಿಸಿ",
    uploadImage: "ಚಿತ್ರ ಅಪ್‌ಲೋಡ್ ಮಾಡಿ",
    analyse: "ಉಪಕರಣವನ್ನು ವಿಶ್ಲೇಷಿಸಿ",
    analysing: "ವಿಶ್ಲೇಷಿಸಲಾಗುತ್ತಿದೆ...",
    cancel: "ವಿಶ್ಲೇಷಣೆ ರದ್ದುಮಾಡಿ",
    clear: "ಚಿತ್ರ ತೆರವುಗೊಳಿಸಿ",
    inactive: "ನಿಷ್ಕ್ರಿಯ",
    starting: "ಪ್ರಾರಂಭವಾಗುತ್ತಿದೆ...",
    retrying: "ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಲಾಗುತ್ತಿದೆ...",
    detected: "ವಸ್ತು(ಗಳು) ಪತ್ತೆಯಾಗಿವೆ",
    visibleObjects: "ಕಾಣುವ ವಸ್ತು(ಗಳು)",
    liveDetection: "ಲೈವ್ ಗುರುತಿಸುವಿಕೆ:",
    cameraOpened: "ಕ್ಯಾಮೆರಾ ಯಶಸ್ವಿಯಾಗಿ ತೆರೆಯಲಾಗಿದೆ.",
    cameraStopped: "ಕ್ಯಾಮೆರಾವನ್ನು ನಿಲ್ಲಿಸಲಾಗಿದೆ.",
    imageCaptured: "ಚಿತ್ರವನ್ನು ಯಶಸ್ವಿಯಾಗಿ ಸೆರೆಹಿಡಿಯಲಾಗಿದೆ.",
    cancelled: "ಉಪಕರಣದ ವಿಶ್ಲೇಷಣೆಯನ್ನು ರದ್ದುಪಡಿಸಲಾಗಿದೆ.",
    timeout:
      "90 ಸೆಕೆಂಡುಗಳ ನಂತರ ಉಪಕರಣದ ವಿಶ್ಲೇಷಣೆಯ ಸಮಯ ಮುಗಿದಿದೆ. ಸೇವೆ ಕಾರ್ಯನಿರತವಾಗಿರಬಹುದು. ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.",
    cameraUnavailable:
      "ಕ್ಯಾಮೆರಾ ಬಳಸಲು HTTPS ಅಥವಾ localhost ಮತ್ತು ಬೆಂಬಲಿತ ಬ್ರೌಸರ್ ಅಗತ್ಯವಿದೆ.",
    cameraDenied:
      "ಕ್ಯಾಮೆರಾ ಅನುಮತಿ ನಿರಾಕರಿಸಲಾಗಿದೆ. ಬ್ರೌಸರ್ ಸೆಟ್ಟಿಂಗ್‌ಗಳಲ್ಲಿ ಅನುಮತಿ ನೀಡಿ.",
    cameraNotFound: "ಈ ಸಾಧನದಲ್ಲಿ ಕ್ಯಾಮೆರಾ ಕಂಡುಬಂದಿಲ್ಲ.",
    cameraFailed: "ಕ್ಯಾಮೆರಾ ತೆರೆಯಲು ಸಾಧ್ಯವಾಗಲಿಲ್ಲ. ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.",
    cameraNotReady:
      "ಕ್ಯಾಮೆರಾ ಇನ್ನೂ ಸಿದ್ಧವಾಗಿಲ್ಲ. ಸ್ವಲ್ಪ ಕಾಯ್ದು ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.",
    captureFailed: "ಚಿತ್ರ ಸೆರೆಹಿಡಿಯಲು ಸಾಧ್ಯವಾಗಲಿಲ್ಲ. ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.",
    prepareCapture: "ಸೆರೆಹಿಡಿದ ಚಿತ್ರವನ್ನು ಸಿದ್ಧಪಡಿಸಲು ಸಾಧ್ಯವಾಗಲಿಲ್ಲ.",
    prepareFrame: "ಕ್ಯಾಮೆರಾ ಫ್ರೇಮ್ ಸಿದ್ಧಪಡಿಸಲು ಸಾಧ್ಯವಾಗಲಿಲ್ಲ.",
    encodeFrame: "ಕ್ಯಾಮೆರಾ ಫ್ರೇಮ್ ಎನ್‌ಕೋಡ್ ಮಾಡಲು ಸಾಧ್ಯವಾಗಲಿಲ್ಲ.",
    sessionExpired: "ನಿಮ್ಮ ಸೆಷನ್ ಮುಗಿದಿದೆ. ಮತ್ತೆ ಲಾಗಿನ್ ಮಾಡಿ.",
    unauthorizedDetection:
      "ಲೈವ್ ಉಪಕರಣ ಗುರುತಿಸುವಿಕೆಗೆ ನಿಮಗೆ ಅನುಮತಿ ಇಲ್ಲ. ಮತ್ತೆ ಲಾಗಿನ್ ಮಾಡಿ ಅಥವಾ ನಿರ್ವಾಹಕರನ್ನು ಸಂಪರ್ಕಿಸಿ.",
    unauthorizedAnalysis:
      "ಉಪಕರಣ ವಿಶ್ಲೇಷಣೆಗೆ ನಿಮಗೆ ಅನುಮತಿ ಇಲ್ಲ. ಮತ್ತೆ ಲಾಗಿನ್ ಮಾಡಿ ಅಥವಾ ನಿರ್ವಾಹಕರನ್ನು ಸಂಪರ್ಕಿಸಿ.",
    detectionFailed: "ಲೈವ್ ವಸ್ತು ಗುರುತಿಸುವಿಕೆ ವಿಫಲವಾಗಿದೆ.",
    incompleteDetection:
      "ಗುರುತಿಸುವಿಕೆ ಸೇವೆಯಿಂದ ಅಪೂರ್ಣ ಪ್ರತಿಕ್ರಿಯೆ ಬಂದಿದೆ.",
    detectionError: "ಲೈವ್ ಗುರುತಿಸುವಿಕೆಯಲ್ಲಿ ದೋಷ ಸಂಭವಿಸಿದೆ.",
    selectImage: "JPEG, PNG ಅಥವಾ WEBP ಚಿತ್ರವನ್ನು ಆಯ್ಕೆಮಾಡಿ.",
    imageTooLarge: "ಚಿತ್ರದ ಗಾತ್ರ 8 MB ಗಿಂತ ಕಡಿಮೆ ಇರಬೇಕು.",
    capturedTooLarge:
      "ಸೆರೆಹಿಡಿದ ಚಿತ್ರದ ಗಾತ್ರ 8 MB ಮಿತಿಯನ್ನು ಮೀರಿದೆ.",
    selectFirst: "ಮೊದಲು ಉಪಕರಣದ ಚಿತ್ರವನ್ನು ಸೆರೆಹಿಡಿಯಿರಿ ಅಥವಾ ಅಪ್‌ಲೋಡ್ ಮಾಡಿ.",
    invalidResponse:
      "ಸರ್ವರ್‌ನಿಂದ ಓದಲು ಸಾಧ್ಯವಾಗದ ಪ್ರತಿಕ್ರಿಯೆ ಬಂದಿದೆ. ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.",
    analysisFailed: "ಉಪಕರಣದ ಚಿತ್ರ ವಿಶ್ಲೇಷಣೆ ವಿಫಲವಾಗಿದೆ.",
    incompleteAnalysis: "ಸರ್ವರ್‌ನಿಂದ ಅಪೂರ್ಣ ವಿಶ್ಲೇಷಣೆ ಬಂದಿದೆ.",
    invalidAnalysis: "ಸರ್ವರ್‌ನಿಂದ ಅಮಾನ್ಯ ವಿಶ್ಲೇಷಣಾ ಸ್ವರೂಪ ಬಂದಿದೆ.",
    resultError:
      "ಉಪಕರಣದ ಚಿತ್ರವನ್ನು ವಿಶ್ಲೇಷಿಸಲು ಸಾಧ್ಯವಾಗಲಿಲ್ಲ. ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.",
    analysisResult: "ವಿಶ್ಲೇಷಣೆಯ ಫಲಿತಾಂಶ",
    confidence: "ವಿಶ್ವಾಸ ಮಟ್ಟ",
    purpose: "ಉದ್ದೇಶ",
    working: "ಕಾರ್ಯವಿಧಾನ",
    relevance: "IntelliWatch ಗೆ ಸಂಬಂಧ",
    sensors: "ಸೆನ್ಸರ್ ಹೊಂದಾಣಿಕೆ",
    anomalies: "ಸಂಭವನೀಯ ಅಸಾಮಾನ್ಯತೆಗಳು",
    limitations: "ಮಿತಿಗಳು",
    equipmentNotIdentified: "ಉಪಕರಣವನ್ನು ಗುರುತಿಸಲಾಗಿಲ್ಲ",
    confidenceNotSpecified: "ನಿರ್ದಿಷ್ಟಪಡಿಸಿಲ್ಲ",
    verifyIdentity:
      "ಇದು AI ಆಧಾರಿತ ದೃಶ್ಯ ಗುರುತಿಸುವಿಕೆ. ಉಪಕರಣದ ಲೇಬಲ್ ಅಥವಾ ತಾಂತ್ರಿಕ ದಾಖಲೆಗಳೊಂದಿಗೆ ಗುರುತನ್ನು ಪರಿಶೀಲಿಸಿ.",
    noAnomalies: "ಯಾವುದೇ ಸಂಭವನೀಯ ಅಸಾಮಾನ್ಯತೆಗಳನ್ನು ಪಟ್ಟಿ ಮಾಡಿಲ್ಲ.",
    noLimitations: "ಹೆಚ್ಚುವರಿ ಮಿತಿಗಳನ್ನು ಪಟ್ಟಿ ಮಾಡಿಲ್ಲ.",
    disclaimer:
      "ಇದು AI ನೆರವಿನ ದೃಶ್ಯ ಮೌಲ್ಯಮಾಪನ ಮಾತ್ರ; ಪ್ರಮಾಣೀಕೃತ ಇಂಜಿನಿಯರಿಂಗ್ ಪರಿಶೀಲನೆ ಅಲ್ಲ. ಫೋಟೋದಿಂದ ಆಂತರಿಕ ಸ್ಥಿತಿ, ವಿದ್ಯುತ್ ಸುರಕ್ಷತೆ, ಸೆನ್ಸರ್ ಅಳವಡಿಕೆ ಅಥವಾ ಕಾರ್ಯಾಚರಣೆಯ ಮಿತಿಗಳನ್ನು ಖಚಿತಪಡಿಸಲು ಸಾಧ್ಯವಿಲ್ಲ. ನಿರ್ವಹಣೆ ಅಥವಾ ಸುರಕ್ಷತಾ ನಿರ್ಧಾರಗಳಿಗೆ ಈ ಫಲಿತಾಂಶವನ್ನೇ ಏಕೈಕ ಆಧಾರವಾಗಿ ಬಳಸಬೇಡಿ.",
    liveNote:
      "ಲೈವ್ ಗುರುತಿಸುವಿಕೆ ಸಕ್ರಿಯವಾಗಿರುವಾಗ ಆಯ್ದ ಕ್ಯಾಮೆರಾ ಫ್ರೇಮ್‌ಗಳನ್ನು ಬ್ಯಾಕೆಂಡ್‌ಗೆ ಕಳುಹಿಸಲಾಗುತ್ತದೆ. ಅವು ಮೆಮೊರಿಯಲ್ಲಿ ಮಾತ್ರ ಸಂಸ್ಕರಿಸಲ್ಪಡುತ್ತವೆ; ಶಾಶ್ವತವಾಗಿ ದಾಖಲಿಸಲಾಗುವುದಿಲ್ಲ. Gemini ವಿಶ್ಲೇಷಣೆ ಆಯ್ಕೆಮಾಡಿದ ಸ್ಥಿರ ಚಿತ್ರದ ಮೇಲೆ ಪ್ರತ್ಯೇಕವಾಗಿ ನಡೆಯುತ್ತದೆ. ಬೆಂಬಲಿತ ಸ್ವರೂಪಗಳು: JPEG, PNG ಮತ್ತು WEBP. ಗರಿಷ್ಠ ಗಾತ್ರ: 8 MB.",
    detectionNote:
      "ಗುರುತಿಸುವಿಕೆಗೆ ಸಾಮಾನ್ಯ COCO ಆಬ್ಜೆಕ್ಟ್ ಮಾದರಿಯನ್ನು ಬಳಸಲಾಗುತ್ತದೆ. ಇದು ಬೆಂಬಲಿತ ಸಾಮಾನ್ಯ ವಸ್ತುಗಳನ್ನು ಗುರುತಿಸಬಹುದು; ಆದರೆ ವಿಶೇಷ ಕೈಗಾರಿಕಾ ಯಂತ್ರಗಳು, ಆಂತರಿಕ ದೋಷಗಳು ಅಥವಾ ಯಂತ್ರದ ನಿರ್ದಿಷ್ಟ ಭಾಗಗಳನ್ನು ಗುರುತಿಸದೇ ಇರಬಹುದು. ಇದು ಪ್ರಮಾಣೀಕೃತ ಪರಿಶೀಲನೆ ಅಲ್ಲ.",
    purposeUnavailable: "ಉದ್ದೇಶದ ಮಾಹಿತಿ ಲಭ್ಯವಿಲ್ಲ.",
    workingUnavailable: "ಕಾರ್ಯವಿಧಾನದ ಮಾಹಿತಿ ಲಭ್ಯವಿಲ್ಲ.",
    relevanceUnavailable: "IntelliWatch ಸಂಬಂಧಿತ ಮಾಹಿತಿ ಲಭ್ಯವಿಲ್ಲ.",
  },

  ta: {
    eyebrow: "IntelliWatch · AI உதவியுடன் ஆய்வு",
    title: "உபகரணக் காட்சி அடையாளம்",
    description:
      "உபகரணத்தின் புகைப்படத்தை எடுக்கவும் அல்லது பதிவேற்றவும். உபகரணத்தை அடையாளம் கண்டு, அதன் செயல்பாட்டைப் புரிந்துகொண்டு, IntelliWatch சென்சார்கள் மூலம் கண்காணிக்கும் வாய்ப்புகளை அறியவும்.",
    image: "உபகரணப் படம்",
    cameraActive: "கேமரா இயங்குகிறது",
    cameraInactive: "கேமரா நிறுத்தப்பட்டுள்ளது",
    noImage: "உபகரணப் படம் தேர்ந்தெடுக்கப்படவில்லை",
    noImageDescription:
      "படம் எடுக்க கேமராவைத் திறக்கவும் அல்லது ஏற்கனவே உள்ள உபகரணப் படத்தைப் பதிவேற்றவும்.",
    openCamera: "கேமராவைத் திற",
    captureImage: "படம் எடு",
    startDetection: "நேரடி கண்டறிதலைத் தொடங்கு",
    stopDetection: "நேரடி கண்டறிதலை நிறுத்து",
    emergencyStop: "கேமராவை உடனடியாக நிறுத்து",
    uploadImage: "படத்தைப் பதிவேற்று",
    analyse: "உபகரணத்தைப் பகுப்பாய்வு செய்",
    analysing: "பகுப்பாய்வு நடைபெறுகிறது...",
    cancel: "பகுப்பாய்வை ரத்துசெய்",
    clear: "படத்தை நீக்கு",
    inactive: "செயலற்றது",
    starting: "தொடங்குகிறது...",
    retrying: "மீண்டும் முயற்சிக்கிறது...",
    detected: "பொருள்(கள்) கண்டறியப்பட்டன",
    visibleObjects: "தெரியும் பொருள்(கள்)",
    liveDetection: "நேரடி கண்டறிதல்:",
    cameraOpened: "கேமரா வெற்றிகரமாகத் திறக்கப்பட்டது.",
    cameraStopped: "கேமரா நிறுத்தப்பட்டது.",
    imageCaptured: "படம் வெற்றிகரமாக எடுக்கப்பட்டது.",
    cancelled: "உபகரணப் பகுப்பாய்வு ரத்துசெய்யப்பட்டது.",
    timeout:
      "90 விநாடிகளுக்குப் பிறகு பகுப்பாய்வு நேரம் முடிந்தது. சேவை பிஸியாக இருக்கலாம். மீண்டும் முயற்சிக்கவும்.",
    cameraUnavailable:
      "கேமராவைப் பயன்படுத்த HTTPS அல்லது localhost மற்றும் ஆதரிக்கப்படும் உலாவி தேவை.",
    cameraDenied:
      "கேமரா அனுமதி மறுக்கப்பட்டது. உலாவி அமைப்புகளில் கேமரா அனுமதியை வழங்கவும்.",
    cameraNotFound: "இந்தச் சாதனத்தில் கேமரா இல்லை.",
    cameraFailed: "கேமராவைத் திறக்க முடியவில்லை. மீண்டும் முயற்சிக்கவும்.",
    cameraNotReady:
      "கேமரா இன்னும் தயாராகவில்லை. காத்திருந்து மீண்டும் முயற்சிக்கவும்.",
    captureFailed: "படம் எடுக்க முடியவில்லை. மீண்டும் முயற்சிக்கவும்.",
    prepareCapture: "எடுக்கப்பட்ட படத்தைத் தயாரிக்க முடியவில்லை.",
    prepareFrame: "கேமரா ஃப்ரேமைத் தயாரிக்க முடியவில்லை.",
    encodeFrame: "கேமரா ஃப்ரேமை குறியாக்கம் செய்ய முடியவில்லை.",
    sessionExpired: "உங்கள் அமர்வு முடிந்துவிட்டது. மீண்டும் உள்நுழையவும்.",
    unauthorizedDetection:
      "நேரடி உபகரணக் கண்டறிதலைப் பயன்படுத்த உங்களுக்கு அனுமதி இல்லை. மீண்டும் உள்நுழையவும் அல்லது நிர்வாகியைத் தொடர்புகொள்ளவும்.",
    unauthorizedAnalysis:
      "உபகரணப் பகுப்பாய்வைப் பயன்படுத்த உங்களுக்கு அனுமதி இல்லை. மீண்டும் உள்நுழையவும் அல்லது நிர்வாகியைத் தொடர்புகொள்ளவும்.",
    detectionFailed: "நேரடி பொருள் கண்டறிதல் தோல்வியடைந்தது.",
    incompleteDetection:
      "கண்டறிதல் சேவையிலிருந்து முழுமையற்ற பதில் வந்துள்ளது.",
    detectionError: "நேரடி கண்டறிதலில் பிழை ஏற்பட்டது.",
    selectImage: "JPEG, PNG அல்லது WEBP படத்தைத் தேர்ந்தெடுக்கவும்.",
    imageTooLarge: "படத்தின் அளவு 8 MB-க்கு குறைவாக இருக்க வேண்டும்.",
    capturedTooLarge:
      "எடுக்கப்பட்ட படத்தின் அளவு 8 MB வரம்பை மீறுகிறது.",
    selectFirst: "முதலில் உபகரணப் படத்தை எடுக்கவும் அல்லது பதிவேற்றவும்.",
    invalidResponse:
      "சேவையகத்திலிருந்து படிக்க முடியாத பதில் வந்துள்ளது. மீண்டும் முயற்சிக்கவும்.",
    analysisFailed: "உபகரணப் படப் பகுப்பாய்வு தோல்வியடைந்தது.",
    incompleteAnalysis: "சேவையகத்திலிருந்து முழுமையற்ற பகுப்பாய்வு வந்துள்ளது.",
    invalidAnalysis: "சேவையகம் தவறான பகுப்பாய்வு வடிவத்தை வழங்கியுள்ளது.",
    resultError:
      "உபகரணப் படத்தைப் பகுப்பாய்வு செய்ய முடியவில்லை. மீண்டும் முயற்சிக்கவும்.",
    analysisResult: "பகுப்பாய்வு முடிவு",
    confidence: "நம்பகத்தன்மை",
    purpose: "பயன்பாடு",
    working: "செயல்படும் முறை",
    relevance: "IntelliWatch தொடர்பு",
    sensors: "சென்சார் பொருத்தம்",
    anomalies: "சாத்தியமான கோளாறுகள்",
    limitations: "வரம்புகள்",
    equipmentNotIdentified: "உபகரணம் அடையாளம் காணப்படவில்லை",
    confidenceNotSpecified: "குறிப்பிடப்படவில்லை",
    verifyIdentity:
      "இது AI உருவாக்கிய காட்சி அடையாளம். உபகரணத்தின் லேபிள் அல்லது தொழில்நுட்ப ஆவணங்களுடன் சரிபார்க்கவும்.",
    noAnomalies: "சாத்தியமான கோளாறுகள் எதுவும் குறிப்பிடப்படவில்லை.",
    noLimitations: "கூடுதல் வரம்புகள் எதுவும் குறிப்பிடப்படவில்லை.",
    disclaimer:
      "இது AI உதவியுடன் செய்யப்பட்ட காட்சி மதிப்பீடு மட்டுமே; சான்றளிக்கப்பட்ட பொறியியல் ஆய்வு அல்ல. புகைப்படத்தால் உள் நிலை, மின்சாரப் பாதுகாப்பு, சென்சார் நிறுவல் அல்லது இயக்க வரம்புகளை உறுதிப்படுத்த முடியாது. பராமரிப்பு அல்லது பாதுகாப்பு முடிவுகளுக்கு இதை மட்டுமே அடிப்படையாகக் கொள்ள வேண்டாம்.",
    liveNote:
      "நேரடி கண்டறிதல் இயங்கும்போது தேர்ந்தெடுக்கப்பட்ட கேமரா ஃப்ரேம்கள் பின்தளத்திற்கு அனுப்பப்படும். அவை நினைவகத்தில் மட்டுமே செயலாக்கப்படும்; நிரந்தரமாகச் சேமிக்கப்படாது. Gemini பகுப்பாய்வு தேர்ந்தெடுக்கப்பட்ட நிலையான படத்தில் தனியாக நடைபெறும். ஆதரிக்கப்படும் வடிவங்கள்: JPEG, PNG மற்றும் WEBP. அதிகபட்ச அளவு: 8 MB.",
    detectionNote:
      "கண்டறிதலுக்கு பொதுவான COCO பொருள் மாதிரி பயன்படுத்தப்படுகிறது. இது ஆதரிக்கப்படும் பொதுவான பொருட்களை அடையாளம் காணலாம்; ஆனால் சிறப்பு தொழில்துறை இயந்திரங்கள், உள் கோளாறுகள் அல்லது குறிப்பிட்ட இயந்திரப் பாகங்களை அடையாளம் காணாமல் போகலாம். இது சான்றளிக்கப்பட்ட ஆய்வு அல்ல.",
    purposeUnavailable: "பயன்பாட்டுத் தகவல் கிடைக்கவில்லை.",
    workingUnavailable: "செயல்பாட்டு முறை பற்றிய தகவல் கிடைக்கவில்லை.",
    relevanceUnavailable: "IntelliWatch தொடர்பான தகவல் கிடைக்கவில்லை.",
  },

  te: {
    eyebrow: "IntelliWatch · AI సహాయంతో తనిఖీ",
    title: "పరికర దృశ్య గుర్తింపు",
    description:
      "పరికరం ఫోటో తీయండి లేదా అప్‌లోడ్ చేయండి. పరికరాన్ని గుర్తించి, దాని పని విధానాన్ని అర్థం చేసుకుని, IntelliWatch సెన్సర్లతో పర్యవేక్షణ అవకాశాలను తెలుసుకోండి.",
    image: "పరికరం చిత్రం",
    cameraActive: "కెమెరా పనిచేస్తోంది",
    cameraInactive: "కెమెరా ఆపివేయబడింది",
    noImage: "పరికరం చిత్రం ఎంచుకోలేదు",
    noImageDescription:
      "చిత్రం తీయడానికి కెమెరాను తెరవండి లేదా ఇప్పటికే ఉన్న పరికరం చిత్రాన్ని అప్‌లోడ్ చేయండి.",
    openCamera: "కెమెరా తెరవండి",
    captureImage: "చిత్రం తీయండి",
    startDetection: "లైవ్ గుర్తింపును ప్రారంభించండి",
    stopDetection: "లైవ్ గుర్తింపును ఆపండి",
    emergencyStop: "కెమెరాను వెంటనే ఆపండి",
    uploadImage: "చిత్రాన్ని అప్‌లోడ్ చేయండి",
    analyse: "పరికరాన్ని విశ్లేషించండి",
    analysing: "విశ్లేషిస్తోంది...",
    cancel: "విశ్లేషణను రద్దు చేయండి",
    clear: "చిత్రాన్ని తొలగించండి",
    inactive: "నిష్క్రియంగా ఉంది",
    starting: "ప్రారంభిస్తోంది...",
    retrying: "మళ్లీ ప్రయత్నిస్తోంది...",
    detected: "వస్తువు(లు) గుర్తించబడ్డాయి",
    visibleObjects: "కనిపించే వస్తువు(లు)",
    liveDetection: "లైవ్ గుర్తింపు:",
    cameraOpened: "కెమెరా విజయవంతంగా తెరవబడింది.",
    cameraStopped: "కెమెరా ఆపివేయబడింది.",
    imageCaptured: "చిత్రం విజయవంతంగా తీయబడింది.",
    cancelled: "పరికర విశ్లేషణ రద్దు చేయబడింది.",
    timeout:
      "90 సెకన్ల తర్వాత పరికర విశ్లేషణ సమయం ముగిసింది. సేవ బిజీగా ఉండవచ్చు. మళ్లీ ప్రయత్నించండి.",
    cameraUnavailable:
      "కెమెరా ఉపయోగించడానికి HTTPS లేదా localhost మరియు మద్దతు ఉన్న బ్రౌజర్ అవసరం.",
    cameraDenied:
      "కెమెరా అనుమతి నిరాకరించబడింది. బ్రౌజర్ సెట్టింగ్‌లలో అనుమతి ఇవ్వండి.",
    cameraNotFound: "ఈ పరికరంలో కెమెరా కనుగొనబడలేదు.",
    cameraFailed: "కెమెరాను తెరవలేకపోయాము. మళ్లీ ప్రయత్నించండి.",
    cameraNotReady:
      "కెమెరా ఇంకా సిద్ధంగా లేదు. కొద్దిసేపు వేచి మళ్లీ ప్రయత్నించండి.",
    captureFailed: "చిత్రం తీయడం విఫలమైంది. మళ్లీ ప్రయత్నించండి.",
    prepareCapture: "తీసిన చిత్రాన్ని సిద్ధం చేయలేకపోయాము.",
    prepareFrame: "కెమెరా ఫ్రేమ్‌ను సిద్ధం చేయలేకపోయాము.",
    encodeFrame: "కెమెరా ఫ్రేమ్‌ను ఎన్‌కోడ్ చేయలేకపోయాము.",
    sessionExpired: "మీ సెషన్ ముగిసింది. దయచేసి మళ్లీ లాగిన్ చేయండి.",
    unauthorizedDetection:
      "లైవ్ పరికర గుర్తింపును ఉపయోగించడానికి మీకు అనుమతి లేదు. మళ్లీ లాగిన్ చేయండి లేదా నిర్వాహకుడిని సంప్రదించండి.",
    unauthorizedAnalysis:
      "పరికర విశ్లేషణను ఉపయోగించడానికి మీకు అనుమతి లేదు. మళ్లీ లాగిన్ చేయండి లేదా నిర్వాహకుడిని సంప్రదించండి.",
    detectionFailed: "లైవ్ వస్తువు గుర్తింపు విఫలమైంది.",
    incompleteDetection:
      "గుర్తింపు సేవ నుండి అసంపూర్ణ సమాధానం వచ్చింది.",
    detectionError: "లైవ్ గుర్తింపులో లోపం ఏర్పడింది.",
    selectImage: "దయచేసి JPEG, PNG లేదా WEBP చిత్రాన్ని ఎంచుకోండి.",
    imageTooLarge: "చిత్ర పరిమాణం 8 MB కంటే తక్కువగా ఉండాలి.",
    capturedTooLarge:
      "తీసిన చిత్రం 8 MB పరిమితిని మించింది.",
    selectFirst: "ముందుగా పరికరం చిత్రాన్ని తీయండి లేదా అప్‌లోడ్ చేయండి.",
    invalidResponse:
      "సర్వర్ నుండి చదవలేని సమాధానం వచ్చింది. మళ్లీ ప్రయత్నించండి.",
    analysisFailed: "పరికర చిత్ర విశ్లేషణ విఫలమైంది.",
    incompleteAnalysis: "సర్వర్ నుండి అసంపూర్ణ విశ్లేషణ వచ్చింది.",
    invalidAnalysis: "సర్వర్ నుండి చెల్లని విశ్లేషణ ఫార్మాట్ వచ్చింది.",
    resultError:
      "పరికర చిత్రాన్ని విశ్లేషించలేకపోయాము. మళ్లీ ప్రయత్నించండి.",
    analysisResult: "విశ్లేషణ ఫలితం",
    confidence: "నమ్మక స్థాయి",
    purpose: "ఉపయోగం",
    working: "పనిచేసే విధానం",
    relevance: "IntelliWatch సంబంధం",
    sensors: "సెన్సర్ అనుకూలత",
    anomalies: "సంభావ్య అసాధారణతలు",
    limitations: "పరిమితులు",
    equipmentNotIdentified: "పరికరం గుర్తించబడలేదు",
    confidenceNotSpecified: "పేర్కొనబడలేదు",
    verifyIdentity:
      "ఇది AI ఆధారిత దృశ్య గుర్తింపు. పరికరం లేబుల్ లేదా సాంకేతిక పత్రాలతో గుర్తింపును ధృవీకరించండి.",
    noAnomalies: "సంభావ్య అసాధారణతలు ఏవీ పేర్కొనబడలేదు.",
    noLimitations: "అదనపు పరిమితులు ఏవీ పేర్కొనబడలేదు.",
    disclaimer:
      "ఇది AI సహాయంతో చేసిన దృశ్య అంచనా మాత్రమే; ధృవీకరించబడిన ఇంజినీరింగ్ తనిఖీ కాదు. ఫోటో ద్వారా అంతర్గత పరిస్థితి, విద్యుత్ భద్రత, సెన్సర్ అమరిక లేదా పరికరం ఆపరేటింగ్ పరిమితులను నిర్ధారించలేము. నిర్వహణ లేదా భద్రతా నిర్ణయాలకు ఈ ఫలితాన్నే ఏకైక ఆధారంగా ఉపయోగించవద్దు.",
    liveNote:
      "లైవ్ గుర్తింపు ప్రారంభమైనప్పుడు ఎంపిక చేసిన కెమెరా ఫ్రేమ్‌లు బ్యాకెండ్‌కు పంపబడతాయి. అవి మెమరీలో మాత్రమే ప్రాసెస్ చేయబడతాయి; శాశ్వతంగా రికార్డ్ లేదా సేవ్ చేయబడవు. Gemini విశ్లేషణ ఎంపిక చేసిన స్థిర చిత్రంపై విడిగా జరుగుతుంది. మద్దతు ఉన్న ఫార్మాట్‌లు: JPEG, PNG మరియు WEBP. గరిష్ఠ పరిమాణం: 8 MB.",
    detectionNote:
      "గుర్తింపు కోసం సాధారణ COCO ఆబ్జెక్ట్ మోడల్ ఉపయోగించబడుతుంది. ఇది మద్దతు ఉన్న సాధారణ వస్తువులను గుర్తించగలదు; కానీ ప్రత్యేక పారిశ్రామిక యంత్రాలు, అంతర్గత లోపాలు లేదా నిర్దిష్ట యంత్ర భాగాలను గుర్తించకపోవచ్చు. ఇది ధృవీకరించబడిన పరికర తనిఖీ కాదు.",
    purposeUnavailable: "ఉపయోగ సమాచారం అందుబాటులో లేదు.",
    workingUnavailable: "పని విధానం సమాచారం అందుబాటులో లేదు.",
    relevanceUnavailable: "IntelliWatch సంబంధిత సమాచారం అందుబాటులో లేదు.",
  },
};

function stopMediaStream(stream) {
  if (stream) {
    stream.getTracks().forEach((track) => track.stop());
  }
}

function calculateIoU(a, b) {
  const x1 = Math.max(a.x1, b.x1);
  const y1 = Math.max(a.y1, b.y1);
  const x2 = Math.min(a.x2, b.x2);
  const y2 = Math.min(a.y2, b.y2);

  const intersectionWidth = Math.max(0, x2 - x1);
  const intersectionHeight = Math.max(0, y2 - y1);
  const intersection = intersectionWidth * intersectionHeight;

  const areaA =
    Math.max(0, a.x2 - a.x1) *
    Math.max(0, a.y2 - a.y1);

  const areaB =
    Math.max(0, b.x2 - b.x1) *
    Math.max(0, b.y2 - b.y1);

  const union = areaA + areaB - intersection;

  return union > 0 ? intersection / union : 0;
}

function getApiErrorMessage(data, fallback) {
  if (typeof data?.detail === "string" && data.detail.trim()) {
    return data.detail;
  }

  if (Array.isArray(data?.detail)) {
    const messages = data.detail
      .map((item) => item?.msg)
      .filter((message) => typeof message === "string");

    if (messages.length > 0) {
      return messages.join("; ");
    }
  }

  if (
    data?.detail &&
    typeof data.detail === "object" &&
    typeof data.detail.message === "string"
  ) {
    return data.detail.message;
  }

  return fallback;
}

function normalizeAnalysis(value, text) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }

  const sensorData =
    value.sensor_compatibility &&
    typeof value.sensor_compatibility === "object" &&
    !Array.isArray(value.sensor_compatibility)
      ? value.sensor_compatibility
      : {};

  const safeSensors = Object.fromEntries(
    Object.entries(sensorData).filter(
      ([, explanation]) => typeof explanation === "string"
    )
  );

  return {
    equipment:
      typeof value.equipment === "string"
        ? value.equipment
        : text("equipmentNotIdentified"),

    confidence:
      typeof value.confidence === "string"
        ? value.confidence
        : text("confidenceNotSpecified"),

    purpose:
      typeof value.purpose === "string"
        ? value.purpose
        : text("purposeUnavailable"),

    working_principle:
      typeof value.working_principle === "string"
        ? value.working_principle
        : text("workingUnavailable"),

    intelliwatch_relevance:
      typeof value.intelliwatch_relevance === "string"
        ? value.intelliwatch_relevance
        : text("relevanceUnavailable"),

    sensor_compatibility: safeSensors,

    possible_anomalies: Array.isArray(value.possible_anomalies)
      ? value.possible_anomalies.filter(
          (item) => typeof item === "string"
        )
      : [],

    limitations: Array.isArray(value.limitations)
      ? value.limitations.filter(
          (item) => typeof item === "string"
        )
      : [],
  };
}

function ResultSection({ title, children }) {
  return (
    <section className="iv-result-section">
      <h3>{title}</h3>
      {children}
    </section>
  );
}

function ResultList({ items, emptyText }) {
  if (!Array.isArray(items) || items.length === 0) {
    return <p className="iv-muted">{emptyText}</p>;
  }

  return (
    <ul className="iv-result-list">
      {items.map((item, index) => (
        <li key={`${index}-${item}`}>{item}</li>
      ))}
    </ul>
  );
}

export default function EquipmentVision() {
  const lang = useLang();

  const selectedLanguage = ["en", "hi", "kn", "ta", "te"].includes(
    String(lang).toLowerCase()
  )
    ? String(lang).toLowerCase()
    : "en";

  const text = (key) =>
    VISION_TEXT[selectedLanguage]?.[key] ??
    VISION_TEXT.en[key] ??
    key;

  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const fileInputRef = useRef(null);
  const previewRef = useRef(null);
  const overlayRef = useRef(null);

  const previewUrlRef = useRef("");
  const detectionActiveRef = useRef(false);
  const detectionTimerRef = useRef(null);
  const detectionInFlightRef = useRef(false);
  const detectionControllerRef = useRef(null);
  const detectionRunIdRef = useRef(0);

  const analysisControllerRef = useRef(null);
  const analysisRequestIdRef = useRef(0);
  const analysisTimerRef = useRef(null);

  const tracksRef = useRef([]);
  const nextTrackIdRef = useRef(1);

  const [cameraActive, setCameraActive] = useState(false);
  const [imageFile, setImageFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [cameraMessage, setCameraMessage] = useState("");

  const [liveDetection, setLiveDetection] = useState(false);
  const [detectionStatus, setDetectionStatus] = useState("Inactive");
  const [detections, setDetections] = useState([]);

  // ==========================================
  // COMPONENT CLEANUP
  // ==========================================

  useEffect(() => {
    return () => {
      detectionActiveRef.current = false;
      detectionRunIdRef.current += 1;
      detectionInFlightRef.current = false;

      analysisRequestIdRef.current += 1;

      if (detectionTimerRef.current) {
        window.clearTimeout(detectionTimerRef.current);
        detectionTimerRef.current = null;
      }

      if (analysisTimerRef.current) {
        window.clearTimeout(analysisTimerRef.current);
        analysisTimerRef.current = null;
      }

      detectionControllerRef.current?.abort();
      analysisControllerRef.current?.abort();

      detectionControllerRef.current = null;
      analysisControllerRef.current = null;

      stopMediaStream(streamRef.current);
      streamRef.current = null;

      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current);
        previewUrlRef.current = "";
      }
    };
  }, []);

  // ==========================================
  // OBJECT TRACKING
  // ==========================================

  function updateTrackedDetections(currentDetections) {
    const previousTracks = tracksRef.current.map((track) => ({
      ...track,
      missed: track.missed + 1,
    }));

    const updatedTracks = [];
    const usedTrackIds = new Set();

    const trackedResults = currentDetections.map((detection) => {
      let bestTrack = null;
      let bestIoU = TRACK_IOU_THRESHOLD;

      for (const track of previousTracks) {
        if (usedTrackIds.has(track.id)) continue;
        if (track.class_id !== detection.class_id) continue;

        const iou = calculateIoU(track.box, detection);

        if (iou > bestIoU) {
          bestIoU = iou;
          bestTrack = track;
        }
      }

      let trackId;

      if (bestTrack) {
        trackId = bestTrack.id;
        usedTrackIds.add(trackId);
      } else {
        trackId = nextTrackIdRef.current++;
      }

      updatedTracks.push({
        id: trackId,
        class_id: detection.class_id,
        label: detection.label,
        box: {
          x1: detection.x1,
          y1: detection.y1,
          x2: detection.x2,
          y2: detection.y2,
        },
        missed: 0,
      });

      return {
        ...detection,
        track_id: trackId,
      };
    });

    for (const track of previousTracks) {
      if (
        !usedTrackIds.has(track.id) &&
        track.missed <= MAX_MISSED_FRAMES
      ) {
        updatedTracks.push(track);
      }
    }

    tracksRef.current = updatedTracks;

    return trackedResults;
  }

  // ==========================================
  // DRAW DETECTION OVERLAY
  // ==========================================

  function drawDetections() {
    const canvas = overlayRef.current;
    const video = videoRef.current;
    const preview = previewRef.current;

    if (!canvas || !video || !preview) return;

    const width = preview.clientWidth;
    const height = preview.clientHeight;

    if (!width || !height) return;

    const dpr = window.devicePixelRatio || 1;

    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);

    const context = canvas.getContext("2d");

    if (!context) return;

    context.setTransform(dpr, 0, 0, dpr, 0, 0);
    context.clearRect(0, 0, width, height);

    if (!video.videoWidth || !video.videoHeight) return;

    const videoRect = video.getBoundingClientRect();
    const previewRect = preview.getBoundingClientRect();

    const scale = Math.min(
      videoRect.width / video.videoWidth,
      videoRect.height / video.videoHeight
    );

    const renderedWidth = video.videoWidth * scale;
    const renderedHeight = video.videoHeight * scale;

    const offsetX =
      videoRect.left -
      previewRect.left +
      (videoRect.width - renderedWidth) / 2;

    const offsetY =
      videoRect.top -
      previewRect.top +
      (videoRect.height - renderedHeight) / 2;

    context.lineWidth = 2;
    context.font = "12px Arial";

    for (const detection of detections) {
      const x = offsetX + detection.x1 * renderedWidth;
      const y = offsetY + detection.y1 * renderedHeight;

      const boxWidth =
        (detection.x2 - detection.x1) * renderedWidth;

      const boxHeight =
        (detection.y2 - detection.y1) * renderedHeight;

      if (boxWidth <= 0 || boxHeight <= 0) continue;

      const label =
        `${detection.label} #${detection.track_id} ` +
        `${(detection.confidence * 100).toFixed(0)}%`;

      context.strokeStyle = "#16a34a";
      context.strokeRect(x, y, boxWidth, boxHeight);

      const labelWidth = context.measureText(label).width + 12;
      const labelHeight = 21;
      const labelY = Math.max(0, y - labelHeight);

      context.fillStyle = "rgba(22, 163, 74, 0.92)";
      context.fillRect(x, labelY, labelWidth, labelHeight);

      context.fillStyle = "#ffffff";
      context.fillText(label, x + 6, labelY + 15);
    }
  }

  useEffect(() => {
    drawDetections();

    if (!cameraActive) return;

    const handleResize = () => drawDetections();

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
    };
  }, [detections, cameraActive]);

  // ==========================================
  // STOP LIVE DETECTION
  // ==========================================

  function stopLiveDetection() {
    detectionActiveRef.current = false;
    detectionRunIdRef.current += 1;

    if (detectionTimerRef.current) {
      window.clearTimeout(detectionTimerRef.current);
      detectionTimerRef.current = null;
    }

    detectionControllerRef.current?.abort();
    detectionControllerRef.current = null;

    detectionInFlightRef.current = false;

    tracksRef.current = [];
    nextTrackIdRef.current = 1;

    setLiveDetection(false);
    setDetections([]);
    setDetectionStatus(text("inactive"));
  }

  // ==========================================
  // CANCEL EQUIPMENT ANALYSIS
  // ==========================================

  function cancelAnalysis() {
    const controller = analysisControllerRef.current;

    if (!controller) return;

    analysisRequestIdRef.current += 1;
    analysisControllerRef.current = null;

    if (analysisTimerRef.current) {
      window.clearTimeout(analysisTimerRef.current);
      analysisTimerRef.current = null;
    }

    controller.abort();

    setLoading(false);
    setError(text("cancelled"));
  }

  // ==========================================
  // CAMERA CONTROL
  // ==========================================

  function stopCamera() {
    stopLiveDetection();

    stopMediaStream(streamRef.current);
    streamRef.current = null;

    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }

    setCameraActive(false);
    setCameraMessage(text("cameraStopped"));
  }

  async function openCamera() {
    setError("");
    setCameraMessage("");

    if (!navigator.mediaDevices?.getUserMedia) {
      setError(text("cameraUnavailable"));
      return;
    }

    stopCamera();

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: "environment" },
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
        audio: false,
      });

      streamRef.current = stream;

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }

      setCameraActive(true);
      setCameraMessage(text("cameraOpened"));
    } catch (err) {
      stopMediaStream(streamRef.current);
      streamRef.current = null;

      setCameraActive(false);

      if (err?.name === "NotAllowedError") {
        setError(text("cameraDenied"));
      } else if (err?.name === "NotFoundError") {
        setError(text("cameraNotFound"));
      } else {
        setError(err?.message || text("cameraFailed"));
      }
    }
  }

  // ==========================================
  // LIVE DETECTION — FRAME PROCESSING
  // ==========================================

  function scheduleNextDetection(runId) {
    if (
      !detectionActiveRef.current ||
      runId !== detectionRunIdRef.current
    ) {
      return;
    }

    if (detectionTimerRef.current) {
      window.clearTimeout(detectionTimerRef.current);
    }

    detectionTimerRef.current = window.setTimeout(
      () => runDetectionFrame(runId),
      DETECTION_INTERVAL
    );
  }

  async function runDetectionFrame(runId = detectionRunIdRef.current) {
    if (
      !detectionActiveRef.current ||
      runId !== detectionRunIdRef.current ||
      detectionInFlightRef.current
    ) {
      return;
    }

    const video = videoRef.current;

    if (!video || !video.videoWidth || !video.videoHeight) {
      scheduleNextDetection(runId);
      return;
    }

    detectionInFlightRef.current = true;

    const controller = new AbortController();
    detectionControllerRef.current = controller;

    try {
      const scale = Math.min(
        1,
        MAX_FRAME_WIDTH / video.videoWidth
      );

      const canvas = document.createElement("canvas");

      canvas.width = Math.round(video.videoWidth * scale);
      canvas.height = Math.round(video.videoHeight * scale);

      const context = canvas.getContext("2d");

      if (!context) {
        throw new Error(text("prepareFrame"));
      }

      context.drawImage(
        video,
        0,
        0,
        canvas.width,
        canvas.height
      );

      const blob = await new Promise((resolve) => {
        canvas.toBlob(resolve, "image/jpeg", 0.72);
      });

      if (!blob) {
        throw new Error(text("encodeFrame"));
      }

      if (
        !detectionActiveRef.current ||
        runId !== detectionRunIdRef.current
      ) {
        return;
      }

      const token = sessionStorage.getItem("iw_token");

      if (!token) {
        stopLiveDetection();
        setError(text("sessionExpired"));
        return;
      }

      const formData = new FormData();

      formData.append(
        "image",
        blob,
        "live-equipment-frame.jpg"
      );

      // Language is intentionally not sent to /vision/detect.
      const response = await fetch(
        `${API_BASE}/vision/detect`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
          },
          body: formData,
          signal: controller.signal,
        }
      );

      const data = await response.json().catch(() => ({}));

      if (
        !detectionActiveRef.current ||
        runId !== detectionRunIdRef.current
      ) {
        return;
      }

      if (!response.ok) {
        if (
          response.status === 401 ||
          response.status === 403
        ) {
          stopLiveDetection();
          setError(text("unauthorizedDetection"));
          return;
        }

        throw new Error(
          getApiErrorMessage(data, text("detectionFailed"))
        );
      }

      if (!data.success || !data.detection) {
        throw new Error(text("incompleteDetection"));
      }

      const detectedObjects = Array.isArray(
        data.detection.detections
      )
        ? data.detection.detections
        : [];

      const trackedResults =
        updateTrackedDetections(detectedObjects);

      setDetections(trackedResults);

      setDetectionStatus(
        `${trackedResults.length} ${text("detected")}`
      );

      setError("");
    } catch (err) {
      if (
        err?.name === "AbortError" ||
        runId !== detectionRunIdRef.current
      ) {
        return;
      }

      if (detectionActiveRef.current) {
        setDetectionStatus(text("retrying"));
        setError(err?.message || text("detectionError"));
      }
    } finally {
      if (detectionControllerRef.current === controller) {
        detectionControllerRef.current = null;
        detectionInFlightRef.current = false;
      }

      if (
        detectionActiveRef.current &&
        runId === detectionRunIdRef.current
      ) {
        scheduleNextDetection(runId);
      }
    }
  }

  function startLiveDetection() {
    if (!cameraActive || !streamRef.current) {
      setError(text("cameraNotReady"));
      return;
    }

    const token = sessionStorage.getItem("iw_token");

    if (!token) {
      setError(text("sessionExpired"));
      return;
    }

    if (detectionActiveRef.current) return;

    setError("");
    tracksRef.current = [];
    nextTrackIdRef.current = 1;

    detectionActiveRef.current = true;
    detectionRunIdRef.current += 1;

    const runId = detectionRunIdRef.current;

    setLiveDetection(true);
    setDetectionStatus(text("starting"));

    runDetectionFrame(runId);
  }

  // ==========================================
  // IMAGE SELECTION
  // ==========================================

  function setSelectedImage(file) {
    if (!file) return;

    if (!SUPPORTED_TYPES.includes(file.type)) {
      setError(text("selectImage"));
      return;
    }

    if (file.size > MAX_IMAGE_SIZE) {
      setError(text("imageTooLarge"));
      return;
    }

    stopCamera();

    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
    }

    const nextPreview = URL.createObjectURL(file);

    previewUrlRef.current = nextPreview;

    setPreviewUrl(nextPreview);
    setImageFile(file);
    setAnalysis(null);
    setError("");
    setCameraMessage("");
  }

  // ==========================================
  // CAPTURE IMAGE
  // ==========================================

  function captureImage() {
    const video = videoRef.current;

    if (!video || !video.videoWidth || !video.videoHeight) {
      setError(text("cameraNotReady"));
      return;
    }

    const maxWidth = 1600;
    const scale = Math.min(1, maxWidth / video.videoWidth);

    const canvas = document.createElement("canvas");

    canvas.width = Math.round(video.videoWidth * scale);
    canvas.height = Math.round(video.videoHeight * scale);

    const context = canvas.getContext("2d");

    if (!context) {
      setError(text("prepareCapture"));
      return;
    }

    context.drawImage(
      video,
      0,
      0,
      canvas.width,
      canvas.height
    );

    canvas.toBlob(
      (blob) => {
        if (!blob) {
          setError(text("captureFailed"));
          return;
        }

        if (blob.size > MAX_IMAGE_SIZE) {
          setError(text("capturedTooLarge"));
          return;
        }

        const file = new File(
          [blob],
          `equipment-capture-${Date.now()}.jpg`,
          { type: "image/jpeg" }
        );

        setSelectedImage(file);
        setCameraMessage(text("imageCaptured"));
      },
      "image/jpeg",
      0.88
    );
  }

  // ==========================================
  // FILE UPLOAD / SELECTION
  // ==========================================

  function handleFileChange(event) {
    const file = event.target.files?.[0];

    if (file) {
      setSelectedImage(file);
    }

    event.target.value = "";
  }

  // ==========================================
  // CLEAR IMAGE
  // ==========================================

  function clearImage() {
    stopCamera();

    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
      previewUrlRef.current = "";
    }

    setImageFile(null);
    setPreviewUrl("");
    setAnalysis(null);
    setError("");
    setCameraMessage("");
  }

  // ==========================================
  // GEMINI EQUIPMENT ANALYSIS
  // ==========================================

  async function analyseEquipment() {
    if (loading || analysisControllerRef.current) {
      return;
    }

    if (!imageFile) {
      setError(text("selectFirst"));
      return;
    }

    const token = sessionStorage.getItem("iw_token");

    if (!token) {
      setError(text("sessionExpired"));
      return;
    }

    stopLiveDetection();

    const requestId = ++analysisRequestIdRef.current;
    const controller = new AbortController();

    analysisControllerRef.current = controller;

    setLoading(true);
    setError("");
    setAnalysis(null);

    // ==========================================
    // HARD UI TIMEOUT
    // ==========================================

    analysisTimerRef.current = window.setTimeout(() => {
      if (
        analysisRequestIdRef.current !== requestId ||
        analysisControllerRef.current !== controller
      ) {
        return;
      }

      analysisRequestIdRef.current += 1;

      analysisControllerRef.current = null;
      analysisTimerRef.current = null;

      controller.abort();

      setLoading(false);
      setError(text("timeout"));
    }, ANALYSIS_TIMEOUT);

    try {
      const formData = new FormData();

      formData.append("image", imageFile);

      // Send the currently selected UI language to Gemini analysis.
      // Supported values: en, hi, kn, ta, te.
      formData.append("language", selectedLanguage);

      const response = await fetch(
        `${API_BASE}/vision/analyse`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
          },
          body: formData,
          signal: controller.signal,
        }
      );

      const responseText = await response.text();

      if (
        analysisRequestIdRef.current !== requestId ||
        controller.signal.aborted
      ) {
        return;
      }

      let data = {};

      if (responseText.trim()) {
        try {
          data = JSON.parse(responseText);
        } catch (parseError) {
          console.error(
            "[EquipmentVision] Invalid analysis JSON:",
            parseError
          );

          throw new Error(text("invalidResponse"));
        }
      }

      if (!response.ok) {
        if (
          response.status === 401 ||
          response.status === 403
        ) {
          throw new Error(text("unauthorizedAnalysis"));
        }

        throw new Error(
          getApiErrorMessage(
            data,
            `${text("analysisFailed")} (HTTP ${response.status}).`
          )
        );
      }

      if (data.success !== true || !data.analysis) {
        throw new Error(
          getApiErrorMessage(data, text("incompleteAnalysis"))
        );
      }

      const normalizedResult = normalizeAnalysis(
        data.analysis,
        text
      );

      if (!normalizedResult) {
        throw new Error(text("invalidAnalysis"));
      }

      if (
        analysisRequestIdRef.current !== requestId ||
        controller.signal.aborted
      ) {
        return;
      }

      setAnalysis(normalizedResult);
      setError("");
    } catch (err) {
      if (analysisRequestIdRef.current !== requestId) {
        return;
      }

      if (err?.name === "AbortError") {
        setError(text("cancelled"));
      } else {
        console.error(
          "[EquipmentVision] Analysis request failed:",
          err
        );

        setError(
          err?.message || text("resultError")
        );
      }
    } finally {
      if (analysisTimerRef.current) {
        window.clearTimeout(analysisTimerRef.current);
        analysisTimerRef.current = null;
      }

      if (analysisRequestIdRef.current === requestId) {
        if (analysisControllerRef.current === controller) {
          analysisControllerRef.current = null;
        }

        setLoading(false);
      }
    }
  }

  const sensorCompatibility =
    analysis?.sensor_compatibility || {};

  return (
    <main className="iv-page">
      <style>{`
        .iv-page {
          width: min(1120px, 100%);
          margin: 0 auto;
          padding: 28px 22px 48px;
          color: var(--text-h);
        }

        .iv-heading {
          margin-bottom: 22px;
        }

        .iv-eyebrow {
          color: var(--muted);
          font-size: 11px;
          font-weight: 700;
          letter-spacing: 1.5px;
          text-transform: uppercase;
          margin-bottom: 8px;
        }

        .iv-heading h1 {
          font-size: clamp(24px, 3vw, 32px);
          line-height: 1.2;
          margin: 0 0 9px;
          color: var(--text-h);
        }

        .iv-heading p {
          color: var(--text);
          font-size: 14px;
          line-height: 1.7;
          max-width: 720px;
        }

        .iv-panel {
          background: var(--bg-card);
          border: 1px solid var(--border);
          border-radius: 16px;
          padding: 22px;
          box-shadow: 0 8px 26px rgba(15, 23, 42, 0.04);
        }

        .iv-panel-heading {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          margin-bottom: 16px;
        }

        .iv-panel-heading h2 {
          color: var(--text-h);
          font-size: 16px;
          margin: 0;
        }

        .iv-status {
          display: inline-flex;
          align-items: center;
          gap: 7px;
          color: var(--muted);
          font-size: 11px;
          font-weight: 600;
        }

        .iv-status-dot {
          width: 7px;
          height: 7px;
          border-radius: 50%;
          background: #94a3b8;
        }

        .iv-status-dot.active {
          background: #16a34a;
          box-shadow: 0 0 0 4px rgba(22, 163, 74, 0.12);
        }

        .iv-preview {
          position: relative;
          display: flex;
          align-items: center;
          justify-content: center;
          min-height: 280px;
          max-height: 520px;
          overflow: hidden;
          border: 1px dashed var(--border);
          border-radius: 12px;
          background: var(--bg-card2);
        }

        .iv-preview img,
        .iv-preview video {
          display: block;
          width: 100%;
          max-height: 520px;
          object-fit: contain;
        }

        .iv-preview video {
          position: relative;
          z-index: 1;
        }

        .iv-overlay {
          position: absolute;
          inset: 0;
          z-index: 2;
          width: 100%;
          height: 100%;
          pointer-events: none;
        }

        .iv-placeholder {
          padding: 48px 20px;
          text-align: center;
          color: var(--muted);
        }

        .iv-placeholder-icon {
          font-size: 36px;
          margin-bottom: 12px;
        }

        .iv-placeholder strong {
          display: block;
          color: var(--text-h);
          font-size: 14px;
          margin-bottom: 6px;
        }

        .iv-placeholder span {
          font-size: 12px;
          line-height: 1.6;
        }

        .iv-actions {
          display: flex;
          flex-wrap: wrap;
          gap: 10px;
          margin-top: 16px;
        }

        .iv-button {
          min-height: 40px;
          border: 1px solid var(--border);
          border-radius: 9px;
          padding: 9px 15px;
          background: var(--bg-card2);
          color: var(--text-h);
          font: inherit;
          font-size: 13px;
          font-weight: 650;
          cursor: pointer;
          transition: opacity .18s ease, transform .18s ease;
        }

        .iv-button:hover:not(:disabled) {
          transform: translateY(-1px);
        }

        .iv-button:disabled {
          opacity: .55;
          cursor: not-allowed;
        }

        .iv-button-primary {
          color: #fff;
          background: #2563eb;
          border-color: #2563eb;
        }

        .iv-button-primary:disabled {
          color: #fff;
          opacity: .8;
        }

        .iv-button-secondary {
          background: transparent;
        }

        .iv-button-live {
          color: #fff;
          background: #15803d;
          border-color: #15803d;
        }

        .iv-button-stop {
          color: #fff;
          background: #b91c1c;
          border-color: #b91c1c;
        }

        .iv-button .iv-spinner {
          display: inline-block;
          width: 14px;
          height: 14px;
          margin-right: 8px;
          vertical-align: -2px;
          border: 2px solid rgba(255, 255, 255, .4);
          border-top-color: #ffffff;
          border-radius: 50%;
          animation: iv-spin .8s linear infinite;
        }

        .iv-detection-status {
          display: flex;
          align-items: center;
          justify-content: space-between;
          flex-wrap: wrap;
          gap: 10px;
          margin-top: 13px;
          padding: 11px 13px;
          border: 1px solid var(--border);
          border-radius: 9px;
          background: var(--bg-card2);
          color: var(--text);
          font-size: 12px;
        }

        .iv-detection-count {
          font-weight: 700;
          color: var(--text-h);
        }

        .iv-note {
          margin-top: 13px;
          color: var(--muted);
          font-size: 11px;
          line-height: 1.6;
        }

        .iv-message {
          margin-top: 14px;
          padding: 12px 14px;
          border-radius: 9px;
          font-size: 13px;
          line-height: 1.5;
        }

        .iv-error {
          color: #b91c1c;
          background: #fee2e2;
          border: 1px solid #fecaca;
        }

        .iv-success {
          color: #166534;
          background: #dcfce7;
          border: 1px solid #bbf7d0;
        }

        @keyframes iv-spin {
          to { transform: rotate(360deg); }
        }

        .iv-results {
          display: grid;
          gap: 14px;
          margin-top: 22px;
        }

        .iv-result-header {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 14px;
          flex-wrap: wrap;
        }

        .iv-result-header h2 {
          margin: 0 0 5px;
          font-size: 19px;
          color: var(--text-h);
        }

        .iv-result-header p {
          margin: 0;
          color: var(--muted);
          font-size: 12px;
        }

        .iv-confidence {
          border: 1px solid var(--border);
          border-radius: 999px;
          padding: 6px 11px;
          color: var(--text);
          font-size: 11px;
          font-weight: 700;
          white-space: nowrap;
        }

        .iv-result-section {
          background: var(--bg-card);
          border: 1px solid var(--border);
          border-radius: 12px;
          padding: 17px 19px;
        }

        .iv-result-section h3 {
          margin: 0 0 10px;
          color: var(--text-h);
          font-size: 13px;
        }

        .iv-result-section p {
          margin: 0;
          color: var(--text);
          font-size: 13px;
          line-height: 1.7;
          overflow-wrap: anywhere;
        }

        .iv-sensor-row {
          padding: 10px 0;
          border-top: 1px solid var(--border);
        }

        .iv-sensor-row:first-of-type {
          border-top: 0;
          padding-top: 0;
        }

        .iv-sensor-row strong {
          display: block;
          margin-bottom: 4px;
          color: var(--text-h);
          font-size: 12px;
        }

        .iv-result-list {
          margin: 0;
          padding-left: 19px;
          color: var(--text);
          font-size: 13px;
          line-height: 1.8;
        }

        .iv-muted {
          color: var(--muted) !important;
          font-size: 12px !important;
        }

        .iv-disclaimer {
          color: var(--muted);
          font-size: 11px;
          line-height: 1.65;
          margin-top: 3px;
        }

        @media (max-width: 640px) {
          .iv-page {
            padding: 20px 13px 34px;
          }

          .iv-panel {
            padding: 15px;
          }

          .iv-preview {
            min-height: 220px;
          }

          .iv-button {
            flex: 1 1 auto;
          }
        }
      `}</style>

      <header className="iv-heading">
        <div className="iv-eyebrow">{text("eyebrow")}</div>

        <h1>{text("title")}</h1>

        <p>{text("description")}</p>
      </header>

      <section className="iv-panel">
        <div className="iv-panel-heading">
          <h2>{text("image")}</h2>

          <span className="iv-status">
            <span
              className={`iv-status-dot ${cameraActive ? "active" : ""}`}
            />

            {cameraActive
              ? text("cameraActive")
              : text("cameraInactive")}
          </span>
        </div>

        <div className="iv-preview" ref={previewRef}>
          {previewUrl ? (
            <img
              src={previewUrl}
              alt={text("image")}
            />
          ) : (
            <>
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                aria-label={text("image")}
                style={{
                  display: cameraActive ? "block" : "none",
                }}
              />

              {cameraActive && (
                <canvas
                  ref={overlayRef}
                  className="iv-overlay"
                  aria-hidden="true"
                />
              )}

              {!cameraActive && (
                <div className="iv-placeholder">
                  <div className="iv-placeholder-icon">📷</div>

                  <strong>{text("noImage")}</strong>

                  <span>{text("noImageDescription")}</span>
                </div>
              )}
            </>
          )}
        </div>

        <div className="iv-actions">
          {!previewUrl && !cameraActive && (
            <button
              type="button"
              className="iv-button iv-button-primary"
              onClick={openCamera}
            >
              {text("openCamera")}
            </button>
          )}

          {cameraActive && (
            <>
              <button
                type="button"
                className="iv-button iv-button-primary"
                onClick={captureImage}
              >
                {text("captureImage")}
              </button>

              {!liveDetection ? (
                <button
                  type="button"
                  className="iv-button iv-button-live"
                  onClick={startLiveDetection}
                >
                  {text("startDetection")}
                </button>
              ) : (
                <button
                  type="button"
                  className="iv-button iv-button-stop"
                  onClick={stopLiveDetection}
                >
                  {text("stopDetection")}
                </button>
              )}

              <button
                type="button"
                className="iv-button iv-button-secondary"
                onClick={stopCamera}
              >
                {text("emergencyStop")}
              </button>
            </>
          )}

          <button
            type="button"
            className="iv-button"
            onClick={() => fileInputRef.current?.click()}
            disabled={loading}
          >
            {text("uploadImage")}
          </button>

          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            capture="environment"
            onChange={handleFileChange}
            hidden
          />

          {previewUrl && (
            <>
              <button
                type="button"
                className="iv-button iv-button-primary"
                onClick={analyseEquipment}
                disabled={loading}
                aria-busy={loading}
              >
                {loading ? (
                  <>
                    <span
                      className="iv-spinner"
                      aria-hidden="true"
                    />
                    {text("analysing")}
                  </>
                ) : (
                  text("analyse")
                )}
              </button>

              {loading && (
                <button
                  type="button"
                  className="iv-button iv-button-stop"
                  onClick={cancelAnalysis}
                >
                  {text("cancel")}
                </button>
              )}

              <button
                type="button"
                className="iv-button iv-button-secondary"
                onClick={clearImage}
                disabled={loading}
              >
                {text("clear")}
              </button>
            </>
          )}
        </div>

        {cameraActive && (
          <div className="iv-detection-status">
            <span>
              {text("liveDetection")}{" "}
              <strong>{detectionStatus}</strong>
            </span>

            <span className="iv-detection-count">
              {detections.length} {text("visibleObjects")}
            </span>
          </div>
        )}

        {cameraMessage && (
          <div className="iv-message iv-success" role="status">
            {cameraMessage}
          </div>
        )}

        {error && (
          <div className="iv-message iv-error" role="alert">
            {error}
          </div>
        )}

        <p className="iv-note">{text("liveNote")}</p>

        <p className="iv-note">{text("detectionNote")}</p>
      </section>

      {analysis && (
        <div className="iv-results" aria-live="polite">
          <section className="iv-panel">
            <div className="iv-result-header">
              <div>
                <div className="iv-eyebrow">
                  {text("analysisResult")}
                </div>

                <h2>
                  {analysis.equipment ||
                    text("equipmentNotIdentified")}
                </h2>

                <p>{text("verifyIdentity")}</p>
              </div>

              <span className="iv-confidence">
                {text("confidence")}:{" "}
                {analysis.confidence ||
                  text("confidenceNotSpecified")}
              </span>
            </div>
          </section>

          <ResultSection title={text("purpose")}>
            <p>{analysis.purpose}</p>
          </ResultSection>

          <ResultSection title={text("working")}>
            <p>{analysis.working_principle}</p>
          </ResultSection>

          <ResultSection title={text("relevance")}>
            <p>{analysis.intelliwatch_relevance}</p>
          </ResultSection>

          <ResultSection title={text("sensors")}>
            {Object.entries(sensorCompatibility).map(
              ([sensor, explanation]) => (
                <div className="iv-sensor-row" key={sensor}>
                  <strong>{sensor}</strong>
                  <p>{explanation}</p>
                </div>
              )
            )}
          </ResultSection>

          <ResultSection title={text("anomalies")}>
            <ResultList
              items={analysis.possible_anomalies}
              emptyText={text("noAnomalies")}
            />
          </ResultSection>

          <ResultSection title={text("limitations")}>
            <ResultList
              items={analysis.limitations}
              emptyText={text("noLimitations")}
            />
          </ResultSection>

          <p className="iv-disclaimer">
            {text("disclaimer")}
          </p>
        </div>
      )}
    </main>
  );
}
