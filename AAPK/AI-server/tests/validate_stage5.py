"""Final provider/API validation retained for compatibility with older CI."""
import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    ROOT / "api" / "huggingface.py",
    ROOT / "api" / "openai.py",
    ROOT / "api" / "providers.py",
    ROOT / "api" / "routes.py",
)

for path in REQUIRED:
    assert path.exists(), f"Missing API module: {path}"

for module in ("api.huggingface", "api.openai", "api.providers", "api.routes"):
    importlib.import_module(module)

import server
assert hasattr(server, "AIHandler")
assert not hasattr(server, "start_mdns")
assert not hasattr(server, "_lan_ip")

print("Stage 5 provider validation: OK")
