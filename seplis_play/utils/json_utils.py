from compression import zstd
from typing import Any

import orjson
from pydantic import BaseModel, JsonValue


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


def zstd_json_dumps_bytes(value: JsonValue) -> bytes:
    return zstd.compress(
        orjson.dumps(
            value,
            option=orjson.OPT_UTC_Z | orjson.OPT_NAIVE_UTC,
        )
    )


def zstd_json_loads(value: bytes | bytearray | memoryview) -> JsonValue:
    return orjson.loads(zstd.decompress(bytes(value)))
