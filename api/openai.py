import base64
import os
from urllib.parse import urlparse

import requests

DEFAULT_ENDPOINT = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-4o-mini"


def _endpoint(settings):
    """Return a safe OpenAI Chat Completions endpoint.

    Old AI settings can retain a Google/OpenRouter endpoint after the provider
    is switched. Never send an OpenAI model/token to another provider host.
    A custom endpoint is still allowed when it is clearly OpenAI-compatible.
    """
    configured = str(settings.get("api_endpoint") or "").strip()
    if not configured:
        return DEFAULT_ENDPOINT

    try:
        host = (urlparse(configured).hostname or "").lower()
    except Exception:
        host = ""

    # Stale endpoints from the other built-in providers must never be reused.
    if host.endswith("googleapis.com") or host.endswith("openrouter.ai"):
        print("OPENAI ENDPOINT RESET:", configured, "->", DEFAULT_ENDPOINT)
        return DEFAULT_ENDPOINT

    return configured


def _model(settings):
    return str(settings.get("api_model") or os.getenv("AI_OPENAI_MODEL") or DEFAULT_MODEL).strip()


def _encode_image(image_path):
    if not image_path:
        return None
    if image_path.startswith("/"):
        image_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), image_path.lstrip("/"))
    if not os.path.exists(image_path):
        return None
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _uses_completion_tokens(model):
    """Models that require max_completion_tokens instead of max_tokens."""
    name = str(model or "").strip().lower()
    return name.startswith(("gpt-5", "o1", "o3", "o4"))


def chat(token, settings, system_prompt, prompt, image_path=None, timeout=45):
    endpoint = _endpoint(settings)
    model = _model(settings)
    base64_img = _encode_image(image_path)
    user_content = prompt

    if base64_img:
        user_content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}},
        ]

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    }

    if _uses_completion_tokens(model):
        payload["max_completion_tokens"] = 512
    else:
        payload["max_tokens"] = 512
        payload["temperature"] = 0.7

    print("OPENAI REQUEST:", f"model={model}", f"endpoint={endpoint}")

    try:
        response = requests.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"OpenAI transport error for {model}: {exc}") from exc

    request_id = response.headers.get("x-request-id") or response.headers.get("request-id") or ""
    print(
        "OPENAI RESPONSE:",
        f"status={response.status_code}",
        f"model={model}",
        f"request_id={request_id or 'none'}",
        f"content_type={response.headers.get('content-type', '') or 'unknown'}",
        f"body_chars={len(response.text or '')}",
    )

    try:
        data = response.json()
    except Exception:
        data = {"error": (response.text or "")[:1200]}

    if response.status_code >= 400 or not isinstance(data, dict) or not data.get("choices"):
        body = (response.text or "").strip()
        if len(body) > 1200:
            body = body[:1200] + "..."
        content_type = response.headers.get("content-type", "")
        error_detail = data.get("error") if isinstance(data, dict) else data
        raise RuntimeError(
            f"OpenAI HTTP {response.status_code}; model={model}; "
            f"content_type={content_type or 'unknown'}; "
            f"request_id={request_id or 'none'}; "
            f"error={error_detail!r}; body={body!r}"
        )

    message = data["choices"][0].get("message", {})
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()

    raise RuntimeError(
        f"OpenAI returned no message content for model={model}; "
        f"finish_reason={data['choices'][0].get('finish_reason')!r}; "
        f"request_id={request_id or 'none'}"
    )
