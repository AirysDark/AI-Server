import json
import os

FILE='memory/embeddings.json'


def load():
    if not os.path.exists(FILE):
        return []
    with open(FILE) as f:
        return json.load(f)


def save(data):
    with open(FILE,'w') as f:
        json.dump(data,f,indent=2)


def remember(text):
    data=load()
    data.append({'text':text})
    save(data)


def search(query):
    data=load()
    return [x for x in data if query.lower() in x['text'].lower()]
