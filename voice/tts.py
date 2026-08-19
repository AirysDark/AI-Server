"""Standalone TTS engine for AI Server voice development.

No dependency on server.py or the production chat stack.
Uses Piper when a Piper executable and local voice model are available,
with the existing Termux TTS command as a lightweight fallback.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .config import DEFAULT_VOICE, VOICES_DIR, voice_available, voice_model_path


def _piper_command() -> str | None:
    return shutil.which("piper")


def available_voices() -> list[str]:
    VOICES_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(
        p.stem for p in VOICES_DIR.glob("*.onnx") if voice_available(p.stem)
    )


def speak(text: str, voice: str = DEFAULT_VOICE, output_file: str | Path | None = None) -> Path | None:
    """Speak text using Piper, or Termux TTS when Piper is unavailable.

    If output_file is supplied, Piper writes a WAV file and nothing is played.
    """
    text = str(text or "").strip()
    if not text:
        return None

    piper = _piper_command()
    if piper and voice_available(voice):
        if output_file is None:
            output_file = VOICES_DIR / "last_output.wav"
        output = Path(output_file)
        output.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [piper, "--model", str(voice_model_path(voice)), "--output_file", str(output)],
            input=text,
            text=True,
            check=True,
        )
        return output

    termux = shutil.which("termux-tts-speak")
    if termux:
        subprocess.run([termux, text], check=False)
        return None

    raise RuntimeError("No supported TTS engine is installed")
