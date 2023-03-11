from pydantic import BaseModel, conint
from pydantic.generics import GenericModel
from typing import TypeVar, Generic
from datetime import datetime, date


class Play_server_episode_create(BaseModel):
    series_id: int
    episode_number: conint(ge=1)
    created_at: datetime


class Play_server_movie_create(BaseModel):
    movie_id: int
    created_at: datetime


T = TypeVar('T')


class Page_cursor_result(GenericModel, Generic[T]):
    items: list[T]
    cursor: str | None = None


class Episode(BaseModel):
    title: str | None
    original_title: str | None
    number: int
    season: int | None
    episode: int | None
    air_date: date | None
    air_datetime: datetime | None
    plot: str | None
    runtime: int | None
    rating: float | None

    class Config:
        orm_mode = True