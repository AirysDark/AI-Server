"""Isolated Piper TTS engine adapter.

This module is intentionally independent from the production AI Server.
"""

from .engine import PiperEngine

__all__ = ["PiperEngine"]
