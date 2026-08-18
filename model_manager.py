import os
import platform
import json

CONFIG = "model_profile.json"
MODEL_DIR = "model"

PROFILES = {
    "low": "tinyllama-1.1b-chat.gguf",
    "medium": "phi-3-mini.gguf",
    "high": "gemma-2b.gguf"
}


def detect_profile():
    try:
        import psutil
        ram = psutil.virtual_memory().total / (1024**3)
    except Exception:
        ram = 4

    if ram < 4:
        return "low"
    if ram < 8:
        return "medium"
    return "high"


def setup_profile():
    profile = detect_profile()

    os.makedirs(MODEL_DIR, exist_ok=True)

    data = {
        "device": platform.machine(),
        "profile": profile,
        "model": PROFILES[profile]
    }

    with open(CONFIG, "w") as f:
        json.dump(data, f, indent=2)

    return data


if __name__ == "__main__":
    print(setup_profile())
