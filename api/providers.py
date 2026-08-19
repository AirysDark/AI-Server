"""Central provider router for online AI requests."""
from api.huggingface import chat as huggingface_chat
from api.openai import chat as openai_chat
from api.google import chat as google_chat
from api.openrouter import chat as openrouter_chat


def provider_name(settings):
    value = str(settings.get("api_provider") or settings.get("provider") or "huggingface").strip().lower()
    endpoint = str(settings.get("api_endpoint") or "").strip().lower()
    model = str(settings.get("api_model") or "").strip().lower()
    has_openrouter_key = bool(str(settings.get("openrouter_token") or "").strip())

    # OpenRouter is OpenAI-compatible, and older AI-Server versions stored it
    # as "openai". Recover those settings from their endpoint, model, or the
    # provider-specific credential so they never get routed to api.openai.com.
    if has_openrouter_key or "openrouter.ai" in endpoint or model.startswith("openrouter/") or model.endswith(":free"):
        return "openrouter"
    if value in ("openrouter", "openrouter.ai"):
        return "openrouter"
    if value in ("openai", "openai-compatible", "openai_compatible"):
        return "openai"
    if value in ("google", "google-ai-studio", "google_ai_studio", "gemini"):
        return "google"
    return "huggingface"


def chat(token, settings, system_prompt, prompt, image_path=None, timeout=45, model=None):
    provider = provider_name(settings)
    if provider == "google":
        return google_chat(token, settings, system_prompt, prompt, image_path=image_path, timeout=timeout, model=model)
    if provider == "openrouter":
        return openrouter_chat(token, settings, system_prompt, prompt, image_path=image_path, timeout=timeout)
    if provider == "openai":
        return openai_chat(token, settings, system_prompt, prompt, image_path=image_path, timeout=timeout)
    selected_model = str(model or settings.get("api_model") or "Qwen/Qwen2.5-7B-Instruct")
    return huggingface_chat(token, selected_model, system_prompt, prompt, image_path=image_path, timeout=timeout)
