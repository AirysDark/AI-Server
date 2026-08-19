"""Google AI Studio / Gemini provider.

Keeps Gemini model discovery and request formatting separate from the
OpenAI-compatible and Hugging Face providers, so Gemini model changes can be
made here without changing the main provider router.
"""
import base64
import os
import re
import requests

BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
MODELS_URL = f"{BASE_URL}/models"

TEXT_MODELS = [
    os.getenv("AI_GOOGLE_MODEL", "gemini-3.6-flash"),
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
]

VISION_MODELS = [
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
]


def _base_url(settings=None):
    configured = str((settings or {}).get("api_endpoint") or "").strip().rstrip("/")
    # Older Google settings used the OpenAI-compatible chat endpoint. Keep
    # those settings working while using the native Gemini API module.
    if not configured or "/openai/" in configured:
        return BASE_URL
    if configured.endswith("/generateContent"):
        configured = configured.rsplit("/models/", 1)[0]
    return configured


def _model_name(model):
    model = str(model or "").strip()
    return model.split("/", 1)[1] if model.startswith("models/") else model


def discover_models(token):
    """Return Gemini models available to this API key that support generateContent."""
    if not token:
        return []
    result = []
    page_token = None
    try:
        for _ in range(5):
            params = {"pageSize": 100}
            if page_token:
                params["pageToken"] = page_token
            response = requests.get(
                MODELS_URL,
                headers={"x-goog-api-key": token},
                params=params,
                timeout=15,
            )
            if response.status_code >= 400:
                break
            data = response.json()
            for item in data.get("models", []):
                name = _model_name(item.get("name", ""))
                methods = item.get("supportedGenerationMethods") or []
                if name and "generateContent" in methods:
                    result.append(name)
            page_token = data.get("nextPageToken")
            if not page_token:
                break
    except Exception:
        return []
    seen = set()
    return [m for m in result if not (m in seen or seen.add(m))]


def is_vision_model(model):
    # Gemini Flash 3.x models used by this app support image input.
    text = _model_name(model).lower()
    return text.startswith("gemini-") and "flash" in text


def _encode_image(image_path):
    if not image_path:
        return None
    if image_path.startswith("/"):
        image_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            image_path.lstrip("/"),
        )
    if not os.path.exists(image_path):
        return None
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def chat(token, settings, system_prompt, prompt, image_path=None, timeout=45, model=None):
    model = _model_name(model or (settings or {}).get("api_model") or TEXT_MODELS[0])
    endpoint = f"{_base_url(settings)}/models/{model}:generateContent"
    user_parts = [{"text": prompt}]
    image = _encode_image(image_path)
    if image:
        user_parts.append({"inlineData": {"mimeType": "image/jpeg", "data": image}})

    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": user_parts}],
        "generationConfig": {"maxOutputTokens": 512},
    }
    response = requests.post(
        endpoint,
        headers={"x-goog-api-key": token, "Content-Type": "application/json"},
        json=payload,
        timeout=timeout,
    )
    try:
        data = response.json()
    except Exception:
        data = {"error": response.text[:1000]}
    if response.status_code >= 400:
        raise RuntimeError(str(data))

    candidates = data.get("candidates") or []
    if not candidates:
        raise RuntimeError(str(data))
    parts = (candidates[0].get("content") or {}).get("parts") or []
    text = "".join(str(part.get("text", "")) for part in parts if isinstance(part, dict))
    if not text:
        raise RuntimeError(str(data))
    return text
