"""Password reset and SMTP helpers for AI Server.

SMTP credentials are intentionally read from environment variables and are
never stored in the repository.
"""
import hashlib
import os
import secrets
import smtplib
import ssl
import time
from email.message import EmailMessage

from core.auth import get_accounts, get_sessions, hash_password, normalize_email
from core.config import AUTH_FILE, SESSIONS_FILE, BASE_DIR, PUBLIC_URL
from core.storage import load_json, save_json

RESET_FILE = os.path.join(BASE_DIR, "password_resets.json")
RESET_TTL = 30 * 60


def _token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _load_tokens():
    return load_json(RESET_FILE, {})


def _save_tokens(data):
    save_json(RESET_FILE, data)


def _smtp_config():
    return {
        "host": os.getenv("AI_SMTP_HOST", "smtp.gmail.com"),
        "port": int(os.getenv("AI_SMTP_PORT", "587")),
        "username": os.getenv("AI_SMTP_USERNAME", ""),
        "password": os.getenv("AI_SMTP_PASSWORD", ""),
        "from": os.getenv("AI_SMTP_FROM", os.getenv("AI_SMTP_USERNAME", "")),
    }


def smtp_ready():
    cfg = _smtp_config()
    return bool(cfg["username"] and cfg["password"] and cfg["from"])


def _send_reset_email(email, token):
    cfg = _smtp_config()
    if not smtp_ready():
        raise RuntimeError("SMTP is not configured")

    base = os.getenv("AI_PUBLIC_URL", PUBLIC_URL).rstrip("/")
    link = f"{base}/reset_password.html?token={token}"

    message = EmailMessage()
    message["Subject"] = "AI Server password reset"
    message["From"] = cfg["from"]
    message["To"] = email
    message.set_content(
        "A password reset was requested for your AI Server account.\n\n"
        f"Use this link to choose a new password:\n{link}\n\n"
        "This link expires in 30 minutes and can only be used once.\n\n"
        "If you did not request this, you can safely ignore this email."
    )

    context = ssl.create_default_context()
    with smtplib.SMTP(cfg["host"], cfg["port"], timeout=20) as smtp:
        smtp.ehlo()
        smtp.starttls(context=context)
        smtp.ehlo()
        smtp.login(cfg["username"], cfg["password"])
        smtp.send_message(message)


def request_reset(email):
    email = normalize_email(email)
    accounts = get_accounts()
    user = next(
        ((uid, record) for uid, record in accounts.get("users", {}).items()
         if normalize_email(record.get("email")) == email),
        None,
    )
    if not user:
        return True

    uid = user[0]
    token = secrets.token_urlsafe(48)
    tokens = _load_tokens()
    now = time.time()
    for key, value in list(tokens.items()):
        if now - float(value.get("created", 0)) > RESET_TTL:
            tokens.pop(key, None)
    tokens[_token_hash(token)] = {"user_id": uid, "created": now}
    _save_tokens(tokens)
    _send_reset_email(email, token)
    return True


def reset_password(token, new_password):
    token = str(token or "")
    if not token or len(new_password) < 8:
        return False, "Password must be at least 8 characters."

    tokens = _load_tokens()
    key = _token_hash(token)
    record = tokens.get(key)
    if not record:
        return False, "This reset link is invalid or has expired."
    if time.time() - float(record.get("created", 0)) > RESET_TTL:
        tokens.pop(key, None)
        _save_tokens(tokens)
        return False, "This reset link is invalid or has expired."

    uid = str(record.get("user_id", ""))
    accounts = get_accounts()
    user = accounts.get("users", {}).get(uid)
    if not user:
        tokens.pop(key, None)
        _save_tokens(tokens)
        return False, "This reset link is invalid or has expired."

    user["password"] = hash_password(new_password)
    save_json(AUTH_FILE, accounts)

    sessions = get_sessions()
    for session_token, session in list(sessions.items()):
        if str(session.get("user_id")) == uid:
            sessions.pop(session_token, None)
    save_json(SESSIONS_FILE, sessions)

    tokens.pop(key, None)
    _save_tokens(tokens)
    return True, "Password changed successfully."
