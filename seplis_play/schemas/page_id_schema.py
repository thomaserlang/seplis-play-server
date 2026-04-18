from typing import Literal

from pydantic import BaseModel


class PlayId(BaseModel):
    # only allow series and movie
    type: Literal['series', 'movie']
    movie_id: int | None = None
    series_id: int | None = None
    number: int | None = None
    exp: int
