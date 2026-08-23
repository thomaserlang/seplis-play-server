from compression import zstd
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator, TypeEngine


class ZstdText(TypeDecorator[str]):
    impl = sa.LargeBinary
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine[Any]:
        if dialect.name in ('mysql', 'mariadb'):
            return dialect.type_descriptor(mysql.MEDIUMBLOB())
        return dialect.type_descriptor(sa.LargeBinary())

    def process_bind_param(
        self, value: str | bytes | bytearray | memoryview | None, dialect: Any
    ) -> bytes | None:
        if value is None:
            return None
        if isinstance(value, bytes):
            return value
        if isinstance(value, bytearray | memoryview):
            return bytes(value)
        return zstd.compress(value.encode('utf-8'))

    def process_result_value(
        self, value: bytes | bytearray | memoryview | None, dialect: Any
    ) -> str | None:
        if value is None:
            return None
        return zstd.decompress(bytes(value)).decode('utf-8')
