from typing import Any

import orjson
from pydantic import BaseModel


def default(obj: BaseModel) -> dict:
    if isinstance(obj, BaseModel):
        return obj.model_dump()
    raise TypeError


def json_dumps(obj: Any) -> str:
    return orjson.dumps(
        obj,
        default=default,
        option=orjson.OPT_UTC_Z | orjson.OPT_NAIVE_UTC,
    ).decode('utf-8')


def json_loads(s: str | bytes) -> Any:
    return orjson.loads(s.decode() if isinstance(s, bytes) else s)
