from datetime import date as dt_date
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, conint


class PlayServerEpisodeCreate(BaseModel):
    series_id: int
    episode_number: Annotated[int, conint(ge=1)]
    created_at: datetime


class Episode(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    title: str | None = None
    original_title: str | None = None
    number: int
    season: int | None = None
    episode: int | None = None
    air_date: dt_date | None = None
    air_datetime: datetime | None = None
    plot: str | None = None
    runtime: int | None = None
    rating: float | None = None


class ParsedFileEpisode(BaseModel):
    series_id: int | None = None
    episode_number: int | None = None
    season: int | None = None
    episode: int | None = None
    date: dt_date | None = None
    title: str | None = None
