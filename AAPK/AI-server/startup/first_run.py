import os
import json
from startup.device_detect import detect_device

PROFILE='model_profile.json'


def setup():
    profile = detect_device()
    with open(PROFILE,'w') as f:
        json.dump(profile,f,indent=2)

    os.makedirs('model',exist_ok=True)
    os.makedirs('memory',exist_ok=True)
    os.makedirs('voice',exist_ok=True)

    return profile


if __name__ == '__main__':
    print(setup())
