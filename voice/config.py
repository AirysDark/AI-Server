"""Configuration for the isolated AI voice module.

This module is intentionally standalone. It is not imported by the main
AI Server yet.
"""

from pathlib import Path

VOICE_DIR = Path(__file__).resolve().parent
VOICES_DIR = VOICE_DIR / "voices"
DEFAULT_VOICE = "en_US-lessac-medium"
DEFAULT_LANGUAGE = "en_US"
DEFAULT_SPEED = 1.0

# Piper voices are downloaded separately from the application source.
# Each voice normally consists of <name>.onnx and <name>.onnx.json.
PIPER_VOICE_BASE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main"


def voice_model_path(name: str) -> Path:
    return VOICES_DIR / f"{name}.onnx"


def voice_config_path(name: str) -> Path:
    return VOICES_DIR / f"{name}.onnx.json"


def voice_available(name: str) -> bool:
    return voice_model_path(name).is_file() and voice_config_path(name).is_file()
