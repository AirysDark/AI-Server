"""One-time Stage 6 cleanup helper.

Removes the obsolete mDNS implementation from core/server_impl.py while
leaving the LAN-IP helper intact for the local startup banner.
"""
from pathlib import Path
import re

path = Path("core/server_impl.py")
text = path.read_text(encoding="utf-8")

# Remove mDNS-specific imports; socket remains for _lan_ip().
text = text.replace(
    "import json, os, uuid, re, random, time, hashlib, hmac, secrets, shutil, socket, struct, threading, atexit",
    "import json, os, uuid, re, random, time, hashlib, hmac, secrets, shutil, socket, threading",
)
text = text.replace('MDNS_HOSTNAME = "ai-server.ddns.net"\n', "")

# Keep _lan_ip(), but remove all mDNS state and functions through load_json().
pattern = re.compile(r"\n_mdns_socket = None\n.*?\ndef load_json\(", re.S)
replacement = "\n\ndef load_json("
text, count = pattern.subn(replacement, text, count=1)
if count != 1:
    raise SystemExit("Stage 6 cleanup: mDNS block was not found exactly once")

path.write_text(text, encoding="utf-8")
print("Removed obsolete mDNS implementation from core/server_impl.py")
