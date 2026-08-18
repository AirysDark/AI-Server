"""AI registry, per-AI paths, settings, and lifecycle helpers."""
import os
import shutil
import time
import uuid
import glob

from core.auth import clean_id, current_user, cookie
from core.config import AIS_FILE, MAX_AIS_PER_ACCOUNT, USERS_DIR
from core.storage import load_json, save_json


def get_ai_registry():
    return load_json(AIS_FILE, {"accounts": {}})


def account_root(uid):
    return os.path.join(USERS_DIR, clean_id(uid))


def ais_root(uid):
    return os.path.join(account_root(uid), "ais")


def ai_root(uid, ai_id):
    return os.path.join(ais_root(uid), clean_id(ai_id))


def settings_file(uid, ai_id):
    return os.path.join(ai_root(uid, ai_id), "settings.json")


def conversations_root(uid, ai_id):
    return os.path.join(ai_root(uid, ai_id), "conversations")


def conversation_file(uid, ai_id):
    return os.path.join(conversations_root(uid, ai_id), "current.json")


def legacy_conversation_file(uid, ai_id):
    return os.path.join(ai_root(uid, ai_id), "conversation.json")


def _conversation_payload(value):
    if not isinstance(value, dict):
        return None
    if isinstance(value.get("data"), dict):
        value = value["data"]
    if "conversation" in value and isinstance(value.get("conversation"), list):
        value.setdefault("memory", {})
        value.setdefault("proactive_state", {})
        return value
    return None


def _latest_conversation_archive(uid, ai_id):
    root = conversations_root(uid, ai_id)
    if not os.path.isdir(root):
        return None
    candidates = []
    for path in glob.glob(os.path.join(root, "*.json")):
        if os.path.basename(path) == "current.json":
            continue
        try:
            raw = load_json(path, None)
            data = _conversation_payload(raw)
            if data is None or not data.get("conversation"):
                continue
            stamp = raw.get("updated", data.get("updated", 0)) if isinstance(raw, dict) else 0
            try:
                stamp = float(stamp or 0)
            except Exception:
                stamp = 0
            candidates.append((stamp, os.path.getmtime(path), path, data))
        except Exception:
            continue
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return candidates[0][3]


def blank_settings(uid, ai_id):
    return {
        "user_id": uid, "ai_id": ai_id, "setup_complete": False,
        "ai_name": "", "profile_photo": "", "description": "",
        "background": "", "user_information": "", "user_name": "",
        "personality": "", "instructions": "",
        "config": {"traits": [], "rules": []},
        "features": {"online_ai": True, "learning": True, "long_term_memory": True, "relevant_memory": True, "automatic_images": False, "proactive_images": False},
        "proactive": {"enabled": False},
    }


def load_settings(uid, ai_id):
    data = load_json(settings_file(uid, ai_id), blank_settings(uid, ai_id))
    return data if isinstance(data, dict) else blank_settings(uid, ai_id)


def save_settings(uid, ai_id, data):
    os.makedirs(ai_root(uid, ai_id), exist_ok=True)
    save_json(settings_file(uid, ai_id), data)


def load_conversation(uid, ai_id):
    """Load the AI's conversation, preferring the conversations directory.

    A non-empty current.json is authoritative. If it is empty, recover the
    newest non-empty archive instead of hiding existing conversations behind an
    empty placeholder. Legacy conversation.json remains a final fallback.
    """
    default = {"conversation": [], "memory": {}, "proactive_state": {}}
    path = conversation_file(uid, ai_id)

    if os.path.exists(path):
        data = _conversation_payload(load_json(path, default))
        if data is not None and data.get("conversation"):
            return data

    archived = _latest_conversation_archive(uid, ai_id)
    if archived is not None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        save_json(path, archived)
        return archived

    legacy = legacy_conversation_file(uid, ai_id)
    if os.path.exists(legacy):
        data = _conversation_payload(load_json(legacy, default))
        if data is not None and data.get("conversation"):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            save_json(path, data)
            return data

    if os.path.exists(path):
        data = _conversation_payload(load_json(path, default))
        if data is not None:
            return data
    return default


def save_conversation_data(uid, ai_id, data):
    path = conversation_file(uid, ai_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    save_json(path, data)


def migrate_legacy_ai(uid):
    reg = get_ai_registry()
    account = reg.setdefault("accounts", {}).setdefault(uid, {"ais": [], "active_ai": None})
    if account.get("ais"):
        return account["ais"][0]["ai_id"]
    old_settings = os.path.join(account_root(uid), "settings.json")
    old_conversation = os.path.join(USERS_DIR, uid + ".json")
    if not os.path.exists(old_settings) and not os.path.exists(old_conversation):
        return None
    ai_id = "AI1-" + uuid.uuid4().hex[:12]
    os.makedirs(ai_root(uid, ai_id), exist_ok=True)
    settings = load_json(old_settings, blank_settings(uid, ai_id))
    settings["user_id"] = uid
    settings["ai_id"] = ai_id
    save_json(settings_file(uid, ai_id), settings)
    if os.path.exists(old_conversation):
        save_conversation_data(uid, ai_id, load_json(old_conversation, default_conversation()))
    account["ais"] = [{"ai_id": ai_id, "created": time.time()}]
    account["active_ai"] = ai_id
    save_json(AIS_FILE, reg)
    return ai_id


def default_conversation():
    return {"conversation": [], "memory": {}, "proactive_state": {}}


def ensure_first_ai(uid):
    reg = get_ai_registry()
    account = reg.setdefault("accounts", {}).setdefault(uid, {"ais": [], "active_ai": None})
    if not account.get("ais"):
        migrated = migrate_legacy_ai(uid)
        if migrated:
            return migrated
        return create_ai(uid)
    return account["active_ai"] or account["ais"][0]["ai_id"]


def list_ais(uid):
    ensure_first_ai(uid)
    account = get_ai_registry()["accounts"][uid]
    result = []
    for item in account.get("ais", []):
        ai_id = item["ai_id"]
        settings = load_settings(uid, ai_id)
        result.append({"ai_id": ai_id, "ai_name": settings.get("ai_name") or "Unnamed AI", "profile_photo": settings.get("profile_photo", ""), "setup_complete": bool(settings.get("setup_complete")), "created": item.get("created"), "active": ai_id == account.get("active_ai")})
    return result


def active_ai(handler):
    uid = current_user(handler)
    if not uid:
        return None, None
    reg = get_ai_registry()
    account = reg.get("accounts", {}).get(uid, {})
    ai_id = account.get("active_ai") or (account.get("ais") or [{}])[0].get("ai_id")
    return uid, ai_id


def set_active(uid, ai_id):
    reg = get_ai_registry()
    account = reg.setdefault("accounts", {}).setdefault(uid, {"ais": [], "active_ai": None})
    if ai_id not in {x["ai_id"] for x in account.get("ais", [])}:
        return False
    account["active_ai"] = ai_id
    save_json(AIS_FILE, reg)
    return True


def create_ai(uid):
    reg = get_ai_registry()
    account = reg.setdefault("accounts", {}).setdefault(uid, {"ais": [], "active_ai": None})
    if len(account.get("ais", [])) >= MAX_AIS_PER_ACCOUNT:
        return None
    ai_id = f"AI{len(account.get('ais', [])) + 1}-" + uuid.uuid4().hex[:12]
    os.makedirs(ai_root(uid, ai_id), exist_ok=True)
    save_settings(uid, ai_id, blank_settings(uid, ai_id))
    save_conversation_data(uid, ai_id, {"conversation": [], "memory": {}, "proactive_state": {}, "created": time.time(), "updated": time.time()})
    account["ais"].append({"ai_id": ai_id, "created": time.time()})
    account["active_ai"] = ai_id
    save_json(AIS_FILE, reg)
    return ai_id


def delete_ai(uid, ai_id):
    reg = get_ai_registry()
    account = reg.get("accounts", {}).get(uid)
    if not account or ai_id not in {x["ai_id"] for x in account.get("ais", [])} or len(account["ais"]) <= 1:
        return False
    account["ais"] = [x for x in account["ais"] if x["ai_id"] != ai_id]
    if account.get("active_ai") == ai_id:
        account["active_ai"] = account["ais"][0]["ai_id"]
    shutil.rmtree(ai_root(uid, ai_id), ignore_errors=True)
    save_json(AIS_FILE, reg)
    return True
