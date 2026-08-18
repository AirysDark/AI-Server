import json
import os

MEMORY_FILE = "memory/facts.json"


def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return {"facts": [], "preferences": []}
    with open(MEMORY_FILE) as f:
        return json.load(f)


def save_memory(memory):
    os.makedirs("memory", exist_ok=True)
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)


def remember(category, value):
    memory = load_memory()
    memory.setdefault(category, []).append(value)
    save_memory(memory)


def recall():
    return load_memory()
