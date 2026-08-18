"""Central AI-Server configuration."""
import os

PORT = 47823
PUBLIC_HOSTNAME = "ai-server.ddns.net"
PUBLIC_URL = f"https://{PUBLIC_HOSTNAME}/"
RECENT_CONTEXT_MESSAGES = 10
RELEVANT_MEMORY_LIMIT = 10
PROACTIVE_MIN_MINUTES = 10
PROACTIVE_MAX_MINUTES = 30
MAX_AIS_PER_ACCOUNT = 3
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USERS_DIR = os.path.join(BASE_DIR, "users")
AUTH_FILE = os.path.join(BASE_DIR, "accounts.json")
SESSIONS_FILE = os.path.join(BASE_DIR, "sessions.json")
AIS_FILE = os.path.join(BASE_DIR, "ais.json")
os.makedirs(USERS_DIR, exist_ok=True)
