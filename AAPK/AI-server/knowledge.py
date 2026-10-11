import os
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KNOWLEDGE_DIR = os.path.join(BASE_DIR, "knowledge")


def load_knowledge():
    result = []
    if not os.path.exists(KNOWLEDGE_DIR):
        return ""

    for name in os.listdir(KNOWLEDGE_DIR):
        path = os.path.join(KNOWLEDGE_DIR, name)
        if os.path.isfile(path):
            try:
                if name.endswith(".txt"):
                    result.append(open(path, encoding="utf-8").read())
                elif name.endswith(".json"):
                    result.append(json.dumps(json.load(open(path, encoding="utf-8"))))
            except Exception:
                pass

    return "\n".join(result)
