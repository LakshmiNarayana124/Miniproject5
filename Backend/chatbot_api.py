from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import get_current_user


# Load Backend/.env when python-dotenv is installed.
# Environment variables supplied by the process take precedence.
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent / ".env", override=False)
except ImportError:
    pass


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chatbot", tags=["Chatbot"])

SUPPORTED_LANGUAGES = {"en", "hi", "kn", "ta", "te"}
DIFY_TIMEOUT_SECONDS = 60


class ChatbotMessageRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=8000)
    conversation_id: Optional[str] = Field(default=None, max_length=255)
    language: str = Field(default="en", max_length=5)


def _get_user_identifier(current_user: Any) -> str:
    """Return a stable, non-empty identifier for the authenticated user."""

    possible_fields = ("id", "user_id", "username")

    for field in possible_fields:
        if isinstance(current_user, dict):
            value = current_user.get(field)
        else:
            value = getattr(current_user, field, None)

        if value is not None and str(value).strip():
            return str(value).strip()

    raise HTTPException(
        status_code=401,
        detail="Unable to identify the authenticated user.",
    )


def _get_dify_settings() -> tuple[str, str, Optional[str]]:
    api_key = os.getenv("DIFY_API_KEY", "").strip()

    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="Bolt AI is not configured on the backend.",
        )

    base_url = os.getenv(
        "DIFY_API_BASE_URL",
        "https://api.dify.ai/v1",
    ).strip().rstrip("/")

    parsed = urllib.parse.urlparse(base_url)

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(
            status_code=500,
            detail="The configured Bolt AI service URL is invalid.",
        )

    if not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"

    language_input_name = os.getenv(
        "DIFY_LANGUAGE_INPUT_NAME",
        "",
    ).strip() or None

    return base_url, api_key, language_input_name


def _call_dify(
    *,
    base_url: str,
    api_key: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Perform one blocking Dify Chatflow request."""

    request_data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        url=f"{base_url}/chat-messages",
        data=request_data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=DIFY_TIMEOUT_SECONDS,
        ) as response:
            response_body = response.read()

    except urllib.error.HTTPError as exc:
        logger.warning("Dify Chatflow returned HTTP %s.", exc.code)

        if exc.code in {401, 403}:
            raise HTTPException(
                status_code=502,
                detail="Bolt AI authentication failed. Check the backend Dify API key.",
            ) from exc

        if exc.code == 429:
            raise HTTPException(
                status_code=503,
                detail="Bolt AI is temporarily busy. Please try again shortly.",
            ) from exc

        if exc.code == 400:
            raise HTTPException(
                status_code=502,
                detail=(
                    "The Chatflow rejected the request. Check its required "
                    "input variables and published version."
                ),
            ) from exc

        raise HTTPException(
            status_code=502,
            detail="Bolt could not get a valid response from the AI service.",
        ) from exc

    except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
        logger.warning("Dify Chatflow connection failed.")
        raise HTTPException(
            status_code=503,
            detail="Bolt AI is temporarily unreachable. Please try again.",
        ) from exc

    try:
        result = json.loads(response_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Bolt received an invalid response from the AI service.",
        ) from exc

    if not isinstance(result, dict):
        raise HTTPException(
            status_code=502,
            detail="Bolt received an unexpected response from the AI service.",
        )

    answer = result.get("answer")

    if not isinstance(answer, str) or not answer.strip():
        raise HTTPException(
            status_code=502,
            detail="The AI service returned an empty answer.",
        )

    return result


@router.post("/message")
async def send_chatbot_message(
    request: ChatbotMessageRequest,
    current_user: Any = Depends(get_current_user),
):
    """Send an authenticated user's message to the published Dify Chatflow."""

    query = request.query.strip()

    if not query:
        raise HTTPException(
            status_code=422,
            detail="Please enter a message for Bolt.",
        )

    language = request.language.lower()

    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=422,
            detail="The selected chatbot language is not supported.",
        )

    base_url, api_key, language_input_name = _get_dify_settings()

    inputs: dict[str, Any] = {}

    # Set this only when the published Dify Chatflow has that input variable.
    if language_input_name:
        inputs[language_input_name] = language

    payload: dict[str, Any] = {
        "query": query,
        "inputs": inputs,
        "response_mode": "blocking",
        "user": f"intelliwatch:{_get_user_identifier(current_user)}",
    }

    if request.conversation_id:
        payload["conversation_id"] = request.conversation_id

    result = await asyncio.to_thread(
        _call_dify,
        base_url=base_url,
        api_key=api_key,
        payload=payload,
    )

    return {
        "answer": result["answer"].strip(),
        "conversation_id": result.get("conversation_id"),
        "message_id": result.get("message_id"),
    }