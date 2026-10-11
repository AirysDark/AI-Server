import os
import json

PROFILE='model_profile.json'


def detect_phone():
    ram = 0
    try:
        with open('/proc/meminfo') as f:
            for line in f:
                if line.startswith('MemTotal'):
                    ram=int(line.split()[1])//1024
    except:
        pass

    if ram < 3000:
        model='tiny'
    elif ram < 6000:
        model='small'
    else:
        model='medium'

    return {'ram_mb':ram,'recommended_model':model}


def setup():
    profile=detect_phone()
    with open(PROFILE,'w') as f:
        json.dump(profile,f,indent=2)

    os.makedirs('model',exist_ok=True)
    os.makedirs('memory',exist_ok=True)

    print('AI setup complete')
    print(profile)


if __name__=='__main__':
    setup()
