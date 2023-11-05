from pydantic import BaseModel, ConfigDict, conint
from typing import Literal, TypeVar, Generic
import datetime


class Play_server_episode_create(BaseModel):
    series_id: int
    episode_number: conint(ge=1)
    created_at: datetime.datetime


class Play_server_movie_create(BaseModel):
    movie_id: int
    created_at: datetime.datetime


T = TypeVar('T')


class Page_cursor_result(BaseModel, Generic[T]):
    items: list[T]
    cursor: str | None = None


class Episode(BaseModel):
    title: str | None = None
    original_title: str | None = None
    number: int
    season: int | None = None
    episode: int | None = None
    air_date: datetime.date | None = None
    air_datetime: datetime.datetime | None = None
    plot: str | None = None
    runtime: int | None = None
    rating: float | None = None

    model_config = ConfigDict(
        from_attributes=True,
    )


class Parsed_file_episode(BaseModel):
    series_id: int | None = None
    episode_number: int | None = None
    season: int | None = None
    episode: int | None = None
    date: datetime.date | None = None
    title: str | None = None


class Play_id(BaseModel):
    # only allow series and movie
    type: Literal['series', 'movie']
    movie_id: int | None = None
    series_id: int | None = None
    number: int | None = None
    exp: int