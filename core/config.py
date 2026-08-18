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

# Persistent user/AI data lives outside the application repository.
# On PythonAnywhere set AI_STORAGE_DIR=/home/AirysDarkX2/AI-Server-Storage
STORAGE_DIR = os.path.abspath(os.getenv("AI_STORAGE_DIR", BASE_DIR))
USERS_DIR = os.path.join(STORAGE_DIR, "users")
AUTH_FILE = os.path.join(STORAGE_DIR, "accounts.json")
SESSIONS_FILE = os.path.join(STORAGE_DIR, "sessions.json")
AIS_FILE = os.path.join(STORAGE_DIR, "ais.json")
LEARNING_DIR = os.path.join(STORAGE_DIR, "learning")

os.makedirs(USERS_DIR, exist_ok=True)
os.makedirs(LEARNING_DIR, exist_ok=True)
