import os
import json

PROFILE_FILE = "model_profile.json"


def detect_device():
    memory_kb = 0
    try:
        with open('/proc/meminfo') as f:
            for line in f:
                if line.startswith('MemTotal'):
                    memory_kb = int(line.split()[1])
                    break
    except Exception:
        pass

    ram_mb = memory_kb // 1024

    if ram_mb < 3000:
        model_class = "tiny"
    elif ram_mb < 6000:
        model_class = "small"
    else:
        model_class = "medium"

    profile = {
        "ram_mb": ram_mb,
        "model_class": model_class,
        "platform": "android-termux"
    }

    with open(PROFILE_FILE, "w") as f:
        json.dump(profile, f, indent=2)

    return profile


if __name__ == "__main__":
    print(detect_device())
