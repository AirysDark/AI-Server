"""JSON persistence helpers for AI Server."""
import json
import os
import threading
import uuid


_SAVE_LOCKS = {}
_SAVE_LOCKS_GUARD = threading.Lock()


def _path_lock(path):
    key = os.path.abspath(path)
    with _SAVE_LOCKS_GUARD:
        lock = _SAVE_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _SAVE_LOCKS[key] = lock
        return lock


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    """Atomically save JSON without shared .tmp-file collisions.

    Multiple HTTP requests can save the same AI at nearly the same time
    (chat, proactive activity, settings, etc.).  A single ``path.tmp`` file
    lets concurrent writers overwrite one another's temporary file and can
    make ``os.replace`` fail.  Each target gets a process-local lock and a
    unique temporary filename instead.
    """
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    lock = _path_lock(path)
    with lock:
        tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.{uuid.uuid4().hex}.tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        finally:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except OSError:
                pass
