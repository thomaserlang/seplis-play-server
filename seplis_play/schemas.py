import datetime
from typing import Annotated, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, conint


class PlayServerEpisodeCreate(BaseModel):
    series_id: int
    episode_number: Annotated[int, conint(ge=1)]
    created_at: datetime.datetime


class PlayServerMovieCreate(BaseModel):
    movie_id: int
    created_at: datetime.datetime


T = TypeVar('T')


class PageCursorResult[T](BaseModel):
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


class ParsedFileEpisode(BaseModel):
    series_id: int | None = None
    episode_number: int | None = None
    season: int | None = None
    episode: int | None = None
    date: datetime.date | None = None
    title: str | None = None


class PlayId(BaseModel):
    # only allow series and movie
    type: Literal['series', 'movie']
    movie_id: int | None = None
    series_id: int | None = None
    number: int | None = None
    exp: int
