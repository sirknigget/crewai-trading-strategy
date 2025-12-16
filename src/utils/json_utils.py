import json

def dump_object(object):
    return json.dumps(object, default=lambda o: o.__dict__, indent=2)