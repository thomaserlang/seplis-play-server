from datetime import datetime

from pydantic import BaseModel


class PlayServerMovieCreate(BaseModel):
    movie_id: int
    created_at: datetime
