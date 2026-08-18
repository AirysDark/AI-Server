import json
import os

FILE='memory/facts.json'


def load():
    if not os.path.exists(FILE):
        return {'facts':[], 'preferences':[]}
    with open(FILE) as f:
        return json.load(f)


def search(term):
    data=load()
    results=[]
    term=term.lower()

    for item in data.get('facts',[]):
        if term in str(item).lower():
            results.append(item)

    for item in data.get('preferences',[]):
        if term in str(item).lower():
            results.append(item)

    return results
