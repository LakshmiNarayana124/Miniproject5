
"""
IntelliWatch — Equipment Vision Service

Responsibilities:
1. Validate uploaded equipment images.
2. Analyse images using Google Gemini.
3. Identify equipment and explain its working principle.
4. Evaluate potential relevance of IntelliWatch sensors.
5. Validate and return structured analysis results.
6. Retry temporary model failures using bounded retries.
7. Use a fallback model when the primary model is overloaded.

Security:
- Uses Windows trusted certificates through truststore.
- Maintains standard HTTPS certificate verification.
- Never exposes API keys in logs or responses.
- Processes images in memory without saving them to disk.
"""

import asyncio
import json
import logging
import os
import time

from typing import Any

# Use the operating system's trusted certificate store.
# Keep this before importing Google GenAI and its HTTP dependencies.
import truststore

truststore.inject_into_ssl()

from google import genai
from google.genai import errors, types


logger = logging.getLogger("intelliwatch.vision")


# ============================================================
# 1. SERVICE CONFIGURATION
# ============================================================

MODEL_NAME = "gemini-3.8-flash"

# Fallback candidate for temporary primary-model failures.
FALLBACK_MODEL_NAME = "gemini-3.6-flash"

MODEL_SEQUENCE = (
    (MODEL_NAME, 2),
    (FALLBACK_MODEL_NAME, 1),
)

MAX_IMAGE_SIZE = 8 * 1024 * 1024

SUPPORTED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

# Supported analysis languages.
SUPPORTED_LANGUAGES = {
    "en": "English",
    "hi": "Hindi",
    "kn": "Kannada",
    "ta": "Tamil",
    "te": "Telugu",
}

# Timeout applies to each individual HTTP request.
# The frontend analysis timeout is 90 seconds.
GEMINI_REQUEST_TIMEOUT_MS = 27000

# Retry delay between attempts for temporary failures.
GEMINI_RETRY_DELAY_SECONDS = 1.0

# Only retry temporary server/network failures.
RETRYABLE_STATUS_CODES = {
    408,
    500,
    502,
    503,
    504,
}


# ============================================================
# 2. RESPONSE VALIDATION CONFIGURATION
# ============================================================

REQUIRED_FIELDS = {
    "equipment",
    "confidence",
    "purpose",
    "working_principle",
    "intelliwatch_relevance",
    "sensor_compatibility",
    "possible_anomalies",
    "limitations",
}

REQUIRED_SENSOR_FIELDS = {
    "ADXL345",
    "DS18B20",
    "ACS712",
}

VALID_CONFIDENCE_LEVELS = {
    "High",
    "Medium",
    "Low",
}


# ============================================================
# 3. EQUIPMENT ANALYSIS PROMPT
# ============================================================

VISION_PROMPT = """
You are the equipment identification assistant for IntelliWatch,
an industrial equipment monitoring and decision-support system.

Analyse the supplied photograph and return one valid JSON object
with exactly these fields:

{
  "equipment": "Identified equipment or Unknown",
  "confidence": "High, Medium, or Low",
  "purpose": "What the equipment is used for",
  "working_principle": "How it works",
  "intelliwatch_relevance": "Why monitoring it may be useful",
  "sensor_compatibility": {
    "ADXL345": "Vibration monitoring relevance",
    "DS18B20": "Temperature monitoring relevance",
    "ACS712": "Current monitoring relevance"
  },
  "possible_anomalies": [
    "Possible abnormal conditions"
  ],
  "limitations": [
    "What cannot be established from the photograph"
  ]
}

ENGINEERING AND ACCURACY RULES:

1. Identify equipment only when visual evidence supports it.
2. Never invent a model, manufacturer, rating or specification.
3. If identification is uncertain, explicitly say so.
4. Distinguish visible observations from general engineering
   knowledge and assumptions.
5. Explain sensor compatibility as a possible application,
   not proof that sensors are installed.
6. Consider the ADXL345 for vibration-related monitoring.
7. Consider the DS18B20 for suitable contact-temperature
   monitoring applications.
8. Consider the ACS712 for compatible electrical-current
   measurement applications.
9. Do not claim that a sensor alone establishes equipment safety.
10. Do not provide unsupported electrical ratings or safety limits.
11. Do not diagnose an internal fault from appearance alone.
12. If the image is unclear or does not show equipment,
    identify that limitation.
13. Keep explanations technically useful and concise.
14. Return valid JSON only. Do not include Markdown fences.
"""


# ============================================================
# 4. CUSTOM RESPONSE ERROR
# ============================================================

class VisionResponseError(RuntimeError):
    """Raised when the model produces an invalid analysis response."""


# ============================================================
# 5. LANGUAGE VALIDATION
# ============================================================

def _normalize_language(language: str) -> str:
    """Validate and normalize the requested analysis language."""

    if not isinstance(language, str):
        raise ValueError(
            "Invalid analysis language."
        )

    normalized = language.strip().lower()

    if normalized not in SUPPORTED_LANGUAGES:
        raise ValueError(
            "Unsupported analysis language. "
            "Supported languages: en, hi, kn, ta, te."
        )

    return normalized


def _build_language_instruction(language: str) -> str:
    """Build instructions for multilingual equipment analysis."""

    selected_language = SUPPORTED_LANGUAGES[language]

    return f"""
LANGUAGE REQUIREMENTS:

Write every human-readable analysis value in {selected_language}.

This includes:
- Equipment identification.
- Equipment purpose.
- Working principle.
- IntelliWatch relevance.
- Sensor compatibility explanations.
- Possible anomalies.
- Limitations.

IMPORTANT STRUCTURAL RULES:

1. Keep every JSON field name exactly as provided in the schema.
2. Keep sensor identifiers exactly as provided:
   ADXL345, DS18B20 and ACS712.
3. Keep the confidence value exactly one of these English words:
   High, Medium, Low.
4. Translate explanatory text, not JSON keys or sensor identifiers.
5. Maintain technical accuracy and natural language.
6. Do not mix languages unnecessarily.
7. Return valid JSON only.
"""


# ============================================================
# 6. IMAGE VALIDATION
# ============================================================

def _validate_image(
    image_bytes: bytes,
    mime_type: str,
) -> None:
    """Validate image content availability, size and MIME type."""

    if not isinstance(image_bytes, bytes) or not image_bytes:
        raise ValueError(
            "The uploaded image is empty or invalid."
        )

    if len(image_bytes) > MAX_IMAGE_SIZE:
        raise ValueError(
            "Image exceeds the 8 MB size limit."
        )

    if mime_type not in SUPPORTED_IMAGE_TYPES:
        raise ValueError(
            "Unsupported image format."
        )


# ============================================================
# 7. AI RESPONSE VALIDATION
# ============================================================

def _validate_analysis(result: Any) -> dict:
    """Validate the structure returned by the AI model."""

    if not isinstance(result, dict):
        raise VisionResponseError(
            "The AI response is not a JSON object."
        )

    if not REQUIRED_FIELDS.issubset(result.keys()):
        raise VisionResponseError(
            "The AI response is incomplete."
        )

    string_fields = {
        "equipment",
        "confidence",
        "purpose",
        "working_principle",
        "intelliwatch_relevance",
    }

    for field in string_fields:
        if not isinstance(result.get(field), str):
            raise VisionResponseError(
                f"Invalid response field: {field}"
            )

        if not result[field].strip():
            raise VisionResponseError(
                f"Empty response field: {field}"
            )

    # Prevent unsupported confidence values.
    if result["confidence"] not in VALID_CONFIDENCE_LEVELS:
        result["confidence"] = "Low"

    # Validate sensor compatibility information.
    sensor_data = result.get("sensor_compatibility")

    if not isinstance(sensor_data, dict):
        raise VisionResponseError(
            "Invalid sensor compatibility information."
        )

    for sensor in REQUIRED_SENSOR_FIELDS:
        sensor_value = sensor_data.get(sensor)

        if (
            not isinstance(sensor_value, str)
            or not sensor_value.strip()
        ):
            raise VisionResponseError(
                f"Missing or invalid sensor information: {sensor}"
            )

    # Validate anomaly and limitation lists.
    for field in ("possible_anomalies", "limitations"):
        value = result.get(field)

        if not isinstance(value, list):
            raise VisionResponseError(
                f"Invalid response list: {field}"
            )

        if not all(
            isinstance(item, str) and item.strip()
            for item in value
        ):
            raise VisionResponseError(
                f"Invalid entries in response list: {field}"
            )

    return result


# ============================================================
# 8. GEMINI CLIENT
# ============================================================

def _create_gemini_client(api_key: str):
    """
    Create a Gemini client with bounded HTTP requests.

    SDK automatic retries are disabled because this service
    implements its own bounded retry and fallback sequence.
    """

    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            timeout=GEMINI_REQUEST_TIMEOUT_MS,
            retry_options=types.HttpRetryOptions(
                attempts=1,
            ),
        ),
    )


# ============================================================
# 9. SINGLE MODEL ANALYSIS
# ============================================================

def _generate_model_analysis(
    client,
    model_name: str,
    image_bytes: bytes,
    mime_type: str,
    language: str = "en",
) -> dict:
    """Generate and validate analysis using one Gemini model."""

    language = _normalize_language(language)

    language_instruction = _build_language_instruction(
        language
    )

    response = client.models.generate_content(
        model=model_name,
        contents=[
            VISION_PROMPT,
            language_instruction,
            types.Part.from_bytes(
                data=image_bytes,
                mime_type=mime_type,
            ),
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2,
            max_output_tokens=1200,
        ),
    )

    if not response or not response.text:
        raise VisionResponseError(
            "The AI service returned an empty response."
        )

    try:
        result = json.loads(response.text)

    except json.JSONDecodeError as exc:
        raise VisionResponseError(
            "The AI service returned an invalid JSON response."
        ) from exc

    return _validate_analysis(result)


# ============================================================
# 10. TRANSPORT ERROR CLASSIFICATION
# ============================================================

def _is_retryable_transport_error(exc: Exception) -> bool:
    """Identify temporary connection and timeout failures."""

    if isinstance(
        exc,
        (
            TimeoutError,
            ConnectionError,
            OSError,
        ),
    ):
        return True

    exception_name = type(exc).__name__.lower()

    retryable_names = (
        "timeout",
        "connection",
        "connecterror",
        "readerror",
        "network",
        "remoteprotocol",
    )

    return any(
        marker in exception_name
        for marker in retryable_names
    )


# ============================================================
# 11. MODEL RETRY AND FALLBACK
# ============================================================

def _analyse_with_fallback(
    client,
    image_bytes: bytes,
    mime_type: str,
    language: str = "en",
) -> dict:
    """
    Analyse using the primary model first.

    Primary model:
        Gemini 3.8 Flash.
        Maximum two attempts for eligible temporary failures.

    Fallback:
        Gemini 3.6 Flash.
        One attempt.

    HTTP 503 and 504 immediately trigger fallback instead of
    repeating the primary request.

    Other temporary failures retain bounded retry behaviour.
    Invalid responses are also retried as before.
    """

    language = _normalize_language(language)

    last_error = None
    total_models = len(MODEL_SEQUENCE)

    for model_index, (model_name, max_attempts) in enumerate(
        MODEL_SEQUENCE
    ):

        for attempt in range(max_attempts):

            try:
                logger.info(
                    "Starting equipment image analysis using %s "
                    "(attempt %s/%s).",
                    model_name,
                    attempt + 1,
                    max_attempts,
                )

                result = _generate_model_analysis(
                    client,
                    model_name,
                    image_bytes,
                    mime_type,
                    language,
                )

                logger.info(
                    "Equipment image analysis completed successfully "
                    "using %s.",
                    model_name,
                )

                return result

            except errors.APIError as exc:
                last_error = exc
                status_code = getattr(exc, "code", None)

                if status_code == 429:
                    logger.warning(
                        "Gemini rate limit reached during equipment analysis."
                    )

                    raise RuntimeError(
                        "The equipment analysis service is rate limited. "
                        "Please try again later."
                    ) from exc

                if status_code not in RETRYABLE_STATUS_CODES:
                    logger.error(
                        "Gemini API rejected equipment analysis "
                        "with HTTP status %s.",
                        status_code,
                    )

                    if status_code in (401, 403):
                        message = (
                            "Gemini authentication or model access "
                            "failed. Check API configuration and permissions."
                        )
                    elif status_code == 404:
                        message = (
                            "The requested Gemini model is unavailable "
                            "for this API configuration."
                        )
                    else:
                        message = (
                            "The Gemini service rejected the "
                            "equipment analysis request."
                        )

                    raise RuntimeError(message) from exc

                logger.warning(
                    "Gemini model %s returned temporary HTTP %s.",
                    model_name,
                    status_code,
                )

                # Do not repeat the request after HTTP 503 or 504.
                # Proceed directly to the configured fallback.
                if (
                    attempt + 1 < max_attempts
                    and status_code not in (503, 504)
                ):
                    delay = (
                        GEMINI_RETRY_DELAY_SECONDS
                        * (2 ** attempt)
                    )

                    logger.info(
                        "Retrying %s after %.1f seconds.",
                        model_name,
                        delay,
                    )

                    time.sleep(delay)
                    continue

                # Move to the next model, if one is available.
                break

            except VisionResponseError as exc:
                last_error = exc

                logger.warning(
                    "Model %s returned an invalid analysis response: %s",
                    model_name,
                    exc,
                )

                if attempt + 1 < max_attempts:
                    time.sleep(0.5)
                    continue

                break

            except Exception as exc:
                if not _is_retryable_transport_error(exc):
                    logger.exception(
                        "Unexpected equipment analysis failure "
                        "using model %s.",
                        model_name,
                    )

                    raise RuntimeError(
                        "Equipment image analysis service failed."
                    ) from exc

                last_error = exc

                logger.warning(
                    "Temporary connection or timeout failure "
                    "using model %s.",
                    model_name,
                )

                if attempt + 1 < max_attempts:
                    time.sleep(GEMINI_RETRY_DELAY_SECONDS)
                    continue

                break

        if model_index + 1 < total_models:
            next_model = MODEL_SEQUENCE[model_index + 1][0]

            logger.warning(
                "Switching equipment analysis from %s to fallback %s.",
                model_name,
                next_model,
            )

    # All configured model attempts have failed.
    if isinstance(last_error, errors.APIError):
        status_code = getattr(last_error, "code", None)

        if status_code in (503, 504):
            raise RuntimeError(
                "Gemini is temporarily unavailable. Both the primary "
                "and fallback analysis attempts were unsuccessful. "
                "Please try again shortly."
            ) from last_error

        raise RuntimeError(
            "The Gemini analysis service is temporarily unavailable."
        ) from last_error

    if isinstance(last_error, VisionResponseError):
        raise RuntimeError(
            "The AI models could not produce a valid equipment analysis. "
            "Please try another clear image."
        ) from last_error

    if last_error is not None:
        raise RuntimeError(
            "The equipment analysis request timed out or encountered "
            "a connection failure. Please try again."
        ) from last_error

    logger.error(
        "Equipment analysis completed without a usable model response."
    )

    raise RuntimeError(
        "No usable equipment analysis response was received."
    )


# ============================================================
# 12. EQUIPMENT IMAGE ANALYSIS
# ============================================================

def analyse_equipment_image(
    image_bytes: bytes,
    mime_type: str,
    language: str = "en",
) -> dict:
    """
    Analyse one captured equipment image using Google Gemini.

    Returns:
        dict: Validated equipment analysis.

    Raises:
        ValueError: Invalid image or language input.
        RuntimeError: AI service or response processing failure.
    """

    # Validate before making an external API request.
    _validate_image(
        image_bytes,
        mime_type,
    )

    language = _normalize_language(language)

    # Read API credentials securely from the environment.
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured."
        )

    client = None

    try:
        client = _create_gemini_client(api_key)

        return _analyse_with_fallback(
            client,
            image_bytes,
            mime_type,
            language,
        )

    except (ValueError, RuntimeError):
        raise

    except Exception as exc:
        logger.exception(
            "Equipment image analysis failed unexpectedly."
        )

        raise RuntimeError(
            "Equipment image analysis service failed."
        ) from exc

    finally:
        if client is not None:
            close_client = getattr(
                client,
                "close",
                None,
            )

            if callable(close_client):
                try:
                    close_client()
                except Exception:
                    logger.debug(
                        "Gemini client cleanup encountered an error.",
                        exc_info=True,
                    )


# ============================================================
# 13. ASYNCHRONOUS ANALYSIS WRAPPER
# ============================================================

async def analyse_equipment_image_async(
    image_bytes: bytes,
    mime_type: str,
    language: str = "en",
) -> dict:
    """
    Run synchronous Gemini analysis in a worker thread.

    Prevents the synchronous SDK request from blocking
    FastAPI's asynchronous request handling.

    The worker performs bounded model attempts and fallback.
    """

    language = _normalize_language(language)

    return await asyncio.to_thread(
        analyse_equipment_image,
        image_bytes,
        mime_type,
        language,
    )
