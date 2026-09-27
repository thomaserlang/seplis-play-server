from typing import TypeVar

from pydantic import BaseModel

T = TypeVar('T')


class PageCursorResult[T](BaseModel):
    records: list[T]
    cursor: str | None = None
