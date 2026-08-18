import os
import urllib.request
from model_manager import setup_profile

MODEL_DIR = "model"

# Model URLs are configured here so they can be changed later
MODEL_URLS = {
    "tinyllama-1.1b-chat.gguf": "",
    "phi-3-mini.gguf": "",
    "gemma-2b.gguf": ""
}


def ensure_model():
    profile = setup_profile()
    filename = profile["model"]
    path = os.path.join(MODEL_DIR, filename)

    if os.path.exists(path):
        return path

    url = MODEL_URLS.get(filename)

    if not url:
        print("Model download URL not configured yet:", filename)
        return None

    urllib.request.urlretrieve(url, path)
    return path


if __name__ == "__main__":
    print(ensure_model())
