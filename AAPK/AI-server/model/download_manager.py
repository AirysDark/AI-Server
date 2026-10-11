import os
import json

MODELS='model/models.json'
PROFILE='model_profile.json'


def load_profile():
    if os.path.exists(PROFILE):
        return json.load(open(PROFILE))
    return {'tier':'tiny'}


def check_model():
    model='model/AI.gguf'
    return os.path.exists(model)


def prepare_model():
    if check_model():
        return 'Model ready'

    return 'Model missing - download step required'


if __name__ == '__main__':
    print(prepare_model())
