import orjson
from pydantic import BaseModel

def default(obj: BaseModel):
    if isinstance(obj, BaseModel):
        return obj.model_dump()
    raise TypeError

def json_dumps(obj):
    return orjson.dumps(
        obj,
        default=default,
        option=orjson.OPT_UTC_Z | orjson.OPT_NAIVE_UTC,
    ).decode('utf-8')

def json_loads(s):
    return orjson.loads(s.decode() if isinstance(s, bytes) else s)