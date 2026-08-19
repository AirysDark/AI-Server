"""Authentication and session helpers extracted from the legacy server."""
import hashlib
import hmac
import re
import secrets
import time
from core.config import AUTH_FILE, SESSIONS_FILE
from core.storage import load_json, save_json

def clean_id(uid): return re.sub(r"[^A-Za-z0-9_-]", "", str(uid or ""))[:100]
def normalize_email(value): return str(value or "").strip().lower()
def valid_email(value): return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value))
def hash_password(password):
 salt=secrets.token_hex(16);digest=hashlib.pbkdf2_hmac("sha256",password.encode(),salt.encode(),210000).hex();return salt+":"+digest
def verify_password(password,stored):
 try:
  salt,digest=stored.split(":",1);check=hashlib.pbkdf2_hmac("sha256",password.encode(),salt.encode(),210000).hex();return hmac.compare_digest(check,digest)
 except Exception:return False
def get_accounts(): return load_json(AUTH_FILE,{"users":{}})
def get_sessions(): return load_json(SESSIONS_FILE,{})
def cookie(handler,name):
 for part in handler.headers.get("Cookie","").split(";"):
  part=part.strip()
  if part.startswith(name+"="):return part.split("=",1)[1]
 return ""
def create_session(uid):
 token=secrets.token_urlsafe(48);data=get_sessions();data[token]={"user_id":uid,"created":time.time()};save_json(SESSIONS_FILE,data);return token
def current_user(handler):
 uid=clean_id(get_sessions().get(cookie(handler,"AI_session"),{}).get("user_id")) or None
 if not uid:return None
 if get_accounts().get("users",{}).get(uid,{}).get("banned",False):return None
 return uid
