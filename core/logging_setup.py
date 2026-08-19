"""File logging for AI Server.

Runtime logs are deliberately kept outside AI-Server-Storage. They belong to
this application instance and are written beneath the repository root.
"""
from __future__ import annotations
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(ROOT, "logs")
ACCESS_LOG = os.path.join(LOG_DIR, "access.log")
ERROR_LOG = os.path.join(LOG_DIR, "error.log")
SERVER_LOG = os.path.join(LOG_DIR, "server.log")

_CONFIGURED = False

def setup_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    os.makedirs(LOG_DIR, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    server_handler = RotatingFileHandler(SERVER_LOG, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    server_handler.setFormatter(fmt)
    server_handler.setLevel(logging.INFO)
    error_handler = RotatingFileHandler(ERROR_LOG, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    error_handler.setFormatter(fmt)
    error_handler.setLevel(logging.ERROR)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(server_handler)
    root.addHandler(error_handler)
    class StreamToLog:
        def __init__(self, level): self.level = level
        def write(self, value):
            value = value.strip()
            if value: logging.getLogger("stdout").log(self.level, value)
        def flush(self): pass
    sys.stdout = StreamToLog(logging.INFO)
    sys.stderr = StreamToLog(logging.ERROR)
    _CONFIGURED = True


def log_access(message: str) -> None:
    os.makedirs(LOG_DIR, exist_ok=True)
    logger = logging.getLogger("access")
    if not logger.handlers:
        h = RotatingFileHandler(ACCESS_LOG, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        logger.addHandler(h)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    logger.info(message)
