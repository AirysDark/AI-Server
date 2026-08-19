import base64
import os
import requests

HF_URL = "https://router.huggingface.co/v1/chat/completions"
HF_MODELS_URL = "https://router.huggingface.co/v1/models"

TEXT_MODELS = [
    os.getenv("AI_AI_MODEL", "Qwen/Qwen2.5-7B-Instruct"),
    "Qwen/Qwen3-8B", "Qwen/Qwen3-4B-Instruct-2507", "Qwen/Qwen2.5-7B-Instruct",
    "Qwen/Qwen2.5-3B-Instruct", "Qwen/Qwen2.5-1.5B-Instruct",
    "meta-llama/Llama-3.3-70B-Instruct", "meta-llama/Llama-3.1-8B-Instruct",
    "meta-llama/Llama-3.2-3B-Instruct", "microsoft/Phi-3.5-mini-instruct",
    "google/gemma-3-4b-it", "google/gemma-2-9b-it",
    "mistralai/Mistral-7B-Instruct-v0.3", "HuggingFaceH4/zephyr-7b-beta",
    "openai/gpt-oss-20b", "openai/gpt-oss-120b",
    "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B", "deepseek-ai/DeepSeek-R1-Distill-Qwen-14B",
    "moonshotai/Kimi-K2-Instruct", "zai-org/GLM-4.5-Air",
]

VISION_MODELS = [
    os.getenv("AI_AI_VISION_MODEL", "Qwen/Qwen2.5-VL-7B-Instruct"),
    "Qwen/Qwen2.5-VL-7B-Instruct", "Qwen/Qwen2.5-VL-3B-Instruct",
    "Qwen/Qwen2-VL-7B-Instruct", "meta-llama/Llama-3.2-11B-Vision-Instruct",
    "meta-llama/Llama-3.2-90B-Vision-Instruct", "google/gemma-3-12b-it",
    "google/gemma-3-4b-it", "mistralai/Pixtral-12B-2409",
]


def discover_models(token, vision=False):
    try:
        r = requests.get(HF_MODELS_URL, headers={"Authorization": f"Bearer {token}"}, timeout=15)
        if r.status_code >= 400:
            return []
        data = r.json()
        models = data.get("data", data if isinstance(data, list) else [])
        result = []
        for item in models:
            model_id = item.get("id") if isinstance(item, dict) else item
            if not model_id:
                continue
            text = model_id.lower()
            is_vision = any(x in text for x in ("vl", "vision", "pixtral", "gemma-3"))
            if is_vision == vision:
                result.append(model_id)
        return result[:100]
    except Exception:
        return []


def is_vision_model(model):
    return any(x in model.lower() for x in ("vl", "vision", "pixtral", "gemma-3"))


def encode_image(image_path):
    if not image_path:
        return None
    if image_path.startswith("/"):
        image_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), image_path.lstrip("/"))
    if not os.path.exists(image_path):
        return None
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def chat(token, model, system_prompt, prompt, image_path=None, timeout=45):
    base64_img = encode_image(image_path)
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
    try:
        response = requests.post(
            HF_URL,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
            timeout=timeout,
        )
    except requests.RequestException as e:
        raise RuntimeError(f"Hugging Face connection error: {e}") from e

    try:
        data = response.json()
    except Exception:
        data = {"error": response.text[:500]}

    if response.status_code >= 400:
        error = data.get("error") if isinstance(data, dict) else data
        if isinstance(error, dict):
            error = error.get("message") or error.get("error") or str(error)
        raise RuntimeError(f"Hugging Face HTTP {response.status_code}: {str(error)[:500]}")

    if not isinstance(data, dict) or not data.get("choices"):
        raise RuntimeError(f"Hugging Face returned no choices: {str(data)[:500]}")

    message = data["choices"][0].get("message", {})
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, list):
        content = "".join(str(x.get("text", "")) if isinstance(x, dict) else str(x) for x in content)
    if not content:
        raise RuntimeError("Hugging Face returned an empty response")
    return str(content)
