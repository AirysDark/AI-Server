import base64
import os
import requests

DEFAULT_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openrouter/free"


def _endpoint(settings):
    return str(settings.get("api_endpoint") or DEFAULT_ENDPOINT).strip()


def _model(settings):
    return str(settings.get("api_model") or DEFAULT_MODEL).strip()


def _encode_image(image_path):
    if not image_path:
        return None
    if image_path.startswith("/"):
        image_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), image_path.lstrip("/"))
    if not os.path.exists(image_path):
        return None
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


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
        "max_tokens": 512,
        "temperature": 0.7,
    }
    response = requests.post(
        endpoint,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "HTTP-Referer": str(settings.get("openrouter_http_referer") or "https://ai-server.local"),
            "X-Title": str(settings.get("openrouter_app_title") or "AI-Server"),
        },
        json=payload,
        timeout=timeout,
    )
    try:
        data = response.json()
    except Exception:
        data = {"error": response.text[:500]}
    if response.status_code >= 400 or not data.get("choices"):
        raise RuntimeError(str(data))
    return data["choices"][0]["message"]["content"]
