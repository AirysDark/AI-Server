"""Small route registration boundary for API modules.

The legacy HTTP handler remains compatible; this module provides a stable place
for extracted API route handlers as Stage 5 continues.
"""
from api.providers import provider_name


def health():
    return {"ok": True, "service": "AI-Server"}


def provider_info(settings):
    return {"provider": provider_name(settings)}
