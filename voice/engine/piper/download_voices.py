from __future__ import annotations

import json
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
VOICE_DIR = ROOT / "voices"
CATALOG = ROOT / "voices.json"
BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {destination.name}...")
    with urlopen(url, timeout=120) as response, destination.open("wb") as output:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)


def model_path(voice_id: str) -> tuple[str, str]:
    base, _, speaker = voice_id.partition(":")
    language, name, quality = base.split("-", 2)
    relative = f"{language.split('_', 1)[0]}/{language}/{name}/{quality}/{base}"
    return relative + ".onnx", relative + ".onnx.json"


def main() -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    for voice in catalog["voices"]:
        onnx_rel, json_rel = model_path(voice["id"])
        onnx = VOICE_DIR / Path(onnx_rel).name
        config = VOICE_DIR / Path(json_rel).name
        if not onnx.exists():
            download(f"{BASE}/{onnx_rel}", onnx)
        if not config.exists():
            download(f"{BASE}/{json_rel}", config)
    print("Piper voice download complete.")


if __name__ == "__main__":
    main()
