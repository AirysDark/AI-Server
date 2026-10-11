import os
import json

from pathlib import Path

BASE = Path(__file__).resolve().parent.parent


def ensure_dirs():
    for folder in ["memory", "model", "voice", "logs"]:
        (BASE / folder).mkdir(exist_ok=True)


def boot():
    ensure_dirs()

    profile = BASE / "model_profile.json"
    if not profile.exists():
        profile.write_text(json.dumps({"status": "needs_detection"}, indent=2))

    print("AI startup checks complete")


if __name__ == "__main__":
    boot()
