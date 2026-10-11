"""Lightweight structural validation for the modular AI Server.

This deliberately avoids starting the HTTP server or making network requests.
Run with: python tests/validate_structure.py
"""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "server.py",
    "wsgi.py",
    "core/config.py",
    "core/storage.py",
    "core/auth.py",
    "core/ai_manager.py",
    "core/conversations.py",
    "core/learning.py",
    "api/huggingface.py",
    "api/openai.py",
    "api/providers.py",
    "api/routes.py",
    "chats_api.py",
]

for relative in REQUIRED:
    path = ROOT / relative
    assert path.is_file(), f"Missing required module: {relative}"
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

print(f"Validated {len(REQUIRED)} modular server files.")
