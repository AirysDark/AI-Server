from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional


class PiperEngine:
    """Small isolated wrapper around the Piper executable and local voice catalog."""

    def __init__(self, executable: Optional[str] = None, voices_dir: Optional[str] = None):
        root = Path(__file__).resolve().parent
        self.executable = executable or shutil.which("piper") or "piper"
        self.voices_dir = Path(voices_dir or (root / "voices"))
        self.catalog_file = root / "voices.json"

    def available(self) -> bool:
        if os.path.isabs(self.executable):
            return Path(self.executable).is_file()
        return shutil.which(self.executable) is not None

    def list_voices(self) -> list[str]:
        if self.catalog_file.is_file():
            try:
                data = json.loads(self.catalog_file.read_text(encoding="utf-8"))
                return [str(v["id"]) for v in data.get("voices", [])]
            except (OSError, ValueError, KeyError, TypeError):
                pass
        if not self.voices_dir.exists():
            return []
        return sorted(p.stem for p in self.voices_dir.glob("*.onnx"))

    def resolve_model(self, voice: str) -> tuple[Path, Optional[str]]:
        voice_id, separator, speaker = str(voice).partition(":")
        model = Path(voice_id)
        if not model.suffix:
            model = model.with_suffix(".onnx")
        if not model.is_absolute():
            model = self.voices_dir / model
        if not model.is_file():
            raise FileNotFoundError(f"Piper voice model not found: {model}")
        if not Path(str(model) + ".json").is_file():
            raise FileNotFoundError(f"Piper voice config not found: {model}.json")
        return model, speaker or None

    def synthesize(self, text: str, voice: str, output_file: str) -> str:
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        model, speaker = self.resolve_model(voice)
        output = Path(output_file)
        output.parent.mkdir(parents=True, exist_ok=True)
        cmd = [self.executable, "--model", str(model), "--output_file", str(output)]
        if speaker is not None:
            cmd.extend(["--speaker", speaker])
        completed = subprocess.run(cmd, input=text, text=True, capture_output=True)
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "Piper failed").strip()
            raise RuntimeError(detail)
        return str(output)
