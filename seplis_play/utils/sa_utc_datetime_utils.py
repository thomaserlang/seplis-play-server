from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from dateutil.parser import parse
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator


class UtcDateTime(TypeDecorator):  # type: ignore
    impl = sa.DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(
        self, value: datetime | str | None, dialect: sa.Dialect
    ) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, str):
            value = parse(value)
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        else:
            value = value.astimezone(UTC)
        return value

    def process_result_value(self, value: Any | str, dialect: Dialect) -> Any:
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=UTC)
            else:
                value = value.astimezone(UTC)
        return value
