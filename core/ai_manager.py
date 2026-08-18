"""AI registry, per-AI paths, settings, and lifecycle helpers."""
import os
import shutil
import time
import uuid

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


def conversation_file(uid, ai_id):
    return os.path.join(ai_root(uid, ai_id), "conversation.json")


def ai_photo_dir(uid, ai_id):
    return os.path.join(ai_root(uid, ai_id), "ai_photos")


def upload_dir(uid, ai_id):
    return os.path.join(ai_root(uid, ai_id), "uploads")


def blank_settings(uid, ai_id):
    return {
        "user_id": uid,
        "ai_id": ai_id,
        "setup_complete": False,
        "ai_name": "",
        "profile_photo": "",
        "description": "",
        "background": "",
        "user_information": "",
        "user_name": "",
        "personality": "",
        "instructions": "",
        "config": {"traits": [], "rules": []},
        "features": {
            "online_ai": True,
            "learning": True,
            "long_term_memory": True,
            "relevant_memory": True,
            "automatic_images": False,
            "proactive_images": False,
        },
        "proactive": {"enabled": False},
    }


def load_settings(uid, ai_id):
    data = load_json(settings_file(uid, ai_id), blank_settings(uid, ai_id))
    if not isinstance(data, dict):
        data = blank_settings(uid, ai_id)
    data["user_id"] = uid
    data["ai_id"] = ai_id
    data.setdefault("setup_complete", False)
    data.setdefault("user_name", "")
    return data


def save_settings(uid, ai_id, data):
    data = dict(data or {})
    data["user_id"] = uid
    data["ai_id"] = ai_id
    data["setup_complete"] = True
    save_json(settings_file(uid, ai_id), data)


def load_conversation(uid, ai_id):
    return load_json(
        conversation_file(uid, ai_id),
        {"conversation": [], "memory": {}, "proactive_state": {}},
    )


def save_conversation_data(uid, ai_id, data):
    save_json(conversation_file(uid, ai_id), data)


def migrate_legacy_ai(uid):
    reg = get_ai_registry()
    account = reg.setdefault("accounts", {}).setdefault(
        uid, {"ais": [], "active_ai": None}
    )
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
        save_conversation_data(
            uid,
            ai_id,
            load_json(
                old_conversation,
                {"conversation": [], "memory": {}, "proactive_state": {}},
            ),
        )
    account["ais"] = [{"ai_id": ai_id, "created": time.time()}]
    account["active_ai"] = ai_id
    save_json(AIS_FILE, reg)
    return ai_id


def ensure_first_ai(uid):
    reg = get_ai_registry()
    account = reg.setdefault("accounts", {}).setdefault(
        uid, {"ais": [], "active_ai": None}
    )
    if not account.get("ais"):
        migrated = migrate_legacy_ai(uid)
        if migrated:
            return migrated
        ai_id = "AI1-" + uuid.uuid4().hex[:12]
        os.makedirs(ai_root(uid, ai_id), exist_ok=True)
        save_json(settings_file(uid, ai_id), blank_settings(uid, ai_id))
        account["ais"] = [{"ai_id": ai_id, "created": time.time()}]
        account["active_ai"] = ai_id
        save_json(AIS_FILE, reg)
    return account.get("active_ai") or account["ais"][0]["ai_id"]


def list_ais(uid):
    ensure_first_ai(uid)
    reg = get_ai_registry()
    account = reg["accounts"][uid]
    result = []
    for item in account.get("ais", []):
        ai_id = item["ai_id"]
        settings = load_settings(uid, ai_id)
        result.append(
            {
                "ai_id": ai_id,
                "ai_name": settings.get("ai_name") or "Unnamed AI",
                "profile_photo": settings.get("profile_photo", ""),
                "setup_complete": bool(settings.get("setup_complete")),
                "created": item.get("created"),
                "active": ai_id == account.get("active_ai"),
            }
        )
    return result


def active_ai(handler):
    uid = current_user(handler)
    if not uid:
        return None, None
    ensure_first_ai(uid)
    reg = get_ai_registry()
    account = reg["accounts"][uid]
    valid = {x["ai_id"] for x in account.get("ais", [])}
    ai_id = clean_id(cookie(handler, "AI_active"))
    if ai_id not in valid:
        ai_id = account.get("active_ai")
    if ai_id not in valid:
        ai_id = next(iter(valid))
    account["active_ai"] = ai_id
    save_json(AIS_FILE, reg)
    return uid, ai_id


def set_active(uid, ai_id):
    reg = get_ai_registry()
    account = reg.setdefault("accounts", {}).setdefault(
        uid, {"ais": [], "active_ai": None}
    )
    if ai_id not in {x["ai_id"] for x in account.get("ais", [])}:
        return False
    account["active_ai"] = ai_id
    save_json(AIS_FILE, reg)
    return True


def create_ai(uid):
    reg = get_ai_registry()
    account = reg.setdefault("accounts", {}).setdefault(
        uid, {"ais": [], "active_ai": None}
    )
    if len(account.get("ais", [])) >= MAX_AIS_PER_ACCOUNT:
        return None
    ai_id = f"AI{len(account.get('ais', [])) + 1}-" + uuid.uuid4().hex[:12]
    os.makedirs(ai_root(uid, ai_id), exist_ok=True)
    save_json(settings_file(uid, ai_id), blank_settings(uid, ai_id))
    account["ais"].append({"ai_id": ai_id, "created": time.time()})
    account["active_ai"] = ai_id
    save_json(AIS_FILE, reg)
    return ai_id


def delete_ai(uid, ai_id):
    reg = get_ai_registry()
    account = reg.get("accounts", {}).get(uid)
    if (
        not account
        or ai_id not in {x["ai_id"] for x in account.get("ais", [])}
        or len(account["ais"]) <= 1
    ):
        return False
    account["ais"] = [x for x in account["ais"] if x["ai_id"] != ai_id]
    if account.get("active_ai") == ai_id:
        account["active_ai"] = account["ais"][0]["ai_id"]
    save_json(AIS_FILE, reg)
    shutil.rmtree(ai_root(uid, ai_id), ignore_errors=True)
    return True
