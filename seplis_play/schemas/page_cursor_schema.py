from typing import TypeVar

from pydantic import BaseModel

T = TypeVar('T')


class PageCursorResult[T](BaseModel):
    items: list[T]
    cursor: str | None = None
