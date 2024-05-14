import json

def ser(myobj):
    return json.loads(json.dumps(myobj, indent=4, sort_keys=True, default=str))
