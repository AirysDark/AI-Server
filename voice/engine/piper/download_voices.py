from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
VOICE_DIR = ROOT / "voices"
CATALOG = ROOT / "voices.json"
BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 0:
        print(f"SKIP  {destination}")
        return

    print(f"GET   {url}")
    request = Request(url, headers={"User-Agent": "AI-Server-Piper-Voice-Downloader/1.0"})
    try:
        with urlopen(request, timeout=120) as response, destination.open("wb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
    except (HTTPError, URLError, TimeoutError) as exc:
        destination.unlink(missing_ok=True)
        raise RuntimeError(f"Download failed: {url}\n{exc}") from exc


def model_path(voice_id: str) -> tuple[str, str]:
    base, _, _speaker = voice_id.partition(":")
    language, name, quality = base.split("-", 2)
    relative = f"{language.split('_', 1)[0]}/{language}/{name}/{quality}/{base}"
    return relative + ".onnx", relative + ".onnx.json"


def main() -> int:
    if not CATALOG.exists():
        print(f"Missing catalog: {CATALOG}", file=sys.stderr)
        return 1

    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    voices = catalog.get("voices", [])
    if not voices:
        print("No voices found in voices.json", file=sys.stderr)
        return 1

    failures = 0
    for voice in voices:
        voice_id = voice["id"]
        base_id = voice_id.split(":", 1)[0]
        onnx_rel, json_rel = model_path(voice_id)
        target = VOICE_DIR / base_id
        try:
            download(f"{BASE}/{onnx_rel}", target / f"{base_id}.onnx")
            download(f"{BASE}/{json_rel}", target / f"{base_id}.onnx.json")
        except RuntimeError as exc:
            failures += 1
            print(f"ERROR {voice_id}: {exc}", file=sys.stderr)

    print(f"\nVoices are stored in: {VOICE_DIR}")
    if failures:
        print(f"{failures} voice(s) failed to download.", file=sys.stderr)
        return 1
    print("Piper voice download complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
