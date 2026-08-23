from typing import Any

import sqlalchemy as sa
from pydantic import JsonValue
from sqlalchemy.dialects import mysql
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator, TypeEngine

from seplis_play.utils.json_utils import zstd_json_dumps_bytes, zstd_json_loads


class ZstdJson(TypeDecorator[JsonValue]):
    impl = sa.LargeBinary
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine[Any]:
        if dialect.name in ('mysql', 'mariadb'):
            return dialect.type_descriptor(mysql.MEDIUMBLOB())
        return dialect.type_descriptor(sa.LargeBinary())

    def process_bind_param(
        self, value: JsonValue | bytes | bytearray | memoryview | None, dialect: Any
    ) -> bytes | None:
        if value is None:
            return None
        if isinstance(value, bytes):
            return value
        if isinstance(value, bytearray | memoryview):
            return bytes(value)
        return zstd_json_dumps_bytes(value)

    def process_result_value(
        self, value: bytes | bytearray | memoryview | None, dialect: Any
    ) -> JsonValue | None:
        if value is None:
            return None
        return zstd_json_loads(value)
