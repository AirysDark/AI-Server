"""Image-generation provider used by AI-Server chat.

Generated images are requested from Hugging Face Inference Providers. Provider
safety rules and account permissions still apply.
"""
import os
import time
from urllib.parse import quote

import requests

DEFAULT_IMAGE_MODEL = os.getenv("AI_IMAGE_MODEL", "stabilityai/stable-diffusion-3-medium-diffusers")
FALLBACK_IMAGE_MODELS = (
    DEFAULT_IMAGE_MODEL,
    "black-forest-labs/FLUX.1-Krea-dev",
    "Qwen/Qwen-Image",
    "ByteDance/Hyper-SD",
)


def is_image_request(text):
    text = str(text or "").lower()
    subjects = ("image", "picture", "photo", "portrait", "drawing", "artwork", "wallpaper")
    actions = ("generate", "create", "make", "draw", "render", "show me", "send me")
    return any(x in text for x in subjects) and any(x in text for x in actions)


def _generate_one(token, prompt, model, timeout):
    url = "https://router.huggingface.co/hf-inference/models/" + quote(model, safe="/")
    response = requests.post(
        url,
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "image/png",
            "Content-Type": "application/json",
        },
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
        raise RuntimeError("Hugging Face did not return image bytes")
    extension = ".png" if "png" in content_type else ".webp" if "webp" in content_type else ".jpg"
    return response.content, extension, model


def generate_image_bytes(token, prompt, model=None, timeout=120):
    token = str(token or "").strip()
    if not token:
        raise RuntimeError("A Hugging Face token is required for image generation")

    requested = str(model or "").strip()
    candidates = [requested] if requested else []
    for candidate in FALLBACK_IMAGE_MODELS:
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    errors = []
    for candidate in candidates:
        try:
            result = _generate_one(token, prompt, candidate, timeout)
            print("HF IMAGE GENERATED:", candidate)
            return result
        except Exception as exc:
            print("HF IMAGE MODEL FAILED:")
            print(candidate)
            print(str(exc))
            errors.append("%s: %s" % (candidate, str(exc)))

    raise RuntimeError("Hugging Face image generation failed: " + "; ".join(errors)[:1800])


def generate_to_directory(token, prompt, output_dir, model=None):
    data, extension, used_model = generate_image_bytes(token, prompt, model=model)
    os.makedirs(output_dir, exist_ok=True)
    filename = "generated-%d%s" % (int(time.time() * 1000), extension)
    full_path = os.path.join(output_dir, filename)
    with open(full_path, "wb") as handle:
        handle.write(data)
    return filename, used_model
