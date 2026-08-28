"""Image-generation provider used by AI-Server chat.

Generated images are requested from Hugging Face Inference Providers. Provider
safety rules and account permissions still apply.
"""
import os
import time
from urllib.parse import quote

import requests

# hf-inference changes its hosted image-model catalogue over time. Keep an
# environment override first, then try current known text-to-image models.
DEFAULT_IMAGE_MODEL = os.getenv("AI_IMAGE_MODEL", "stabilityai/stable-diffusion-3-medium-diffusers")
IMAGE_MODELS = [
    DEFAULT_IMAGE_MODEL,
    "stabilityai/stable-diffusion-3-medium-diffusers",
    "black-forest-labs/FLUX.1-Krea-dev",
    "Qwen/Qwen-Image",
    "ByteDance/Hyper-SD",
]


def is_image_request(text):
    text = str(text or "").lower()
    subjects = ("image", "picture", "photo", "portrait", "drawing", "artwork", "wallpaper")
    actions = ("generate", "create", "make", "draw", "render", "show me", "send me")
    return any(x in text for x in subjects) and any(x in text for x in actions)


def _candidate_models(model=None):
    out = []
    for item in ([model] if model else []) + IMAGE_MODELS:
        item = str(item or "").strip()
        if item and item not in out:
            out.append(item)
    return out


def _request_model(token, prompt, model, timeout):
    url = "https://router.huggingface.co/hf-inference/models/" + quote(model, safe="/")
    response = requests.post(
        url,
        headers={"Authorization": "Bearer " + token, "Accept": "image/*", "Content-Type": "application/json"},
        json={"inputs": str(prompt or "").strip()},
        timeout=timeout,
    )
    if response.status_code >= 400:
        try:
            detail = response.json()
        except Exception:
            detail = response.text[:500]
        raise RuntimeError("HTTP %s %s" % (response.status_code, str(detail)[:500]))
    content_type = str(response.headers.get("Content-Type", "")).lower()
    if not response.content or "application/json" in content_type:
        raise RuntimeError("provider returned no image bytes")
    extension = ".png" if "png" in content_type else ".webp" if "webp" in content_type else ".jpg"
    return response.content, extension


def generate_image_bytes(token, prompt, model=None, timeout=120):
    token = str(token or "").strip()
    if not token:
        raise RuntimeError("A Hugging Face token is required for image generation")
    errors = []
    for candidate in _candidate_models(model):
        try:
            data, extension = _request_model(token, prompt, candidate, timeout)
            print("HF IMAGE GENERATED:", candidate)
            return data, extension, candidate
        except Exception as exc:
            errors.append("%s: %s" % (candidate, str(exc)[:300]))
            print("HF IMAGE MODEL FAILED:", candidate, str(exc)[:500])
    raise RuntimeError("Hugging Face image generation failed: " + "; ".join(errors))


def generate_to_directory(token, prompt, output_dir, model=None):
    data, extension, used_model = generate_image_bytes(token, prompt, model=model)
    os.makedirs(output_dir, exist_ok=True)
    filename = "generated-%d%s" % (int(time.time() * 1000), extension)
    full_path = os.path.join(output_dir, filename)
    with open(full_path, "wb") as handle:
        handle.write(data)
    return filename, used_model
