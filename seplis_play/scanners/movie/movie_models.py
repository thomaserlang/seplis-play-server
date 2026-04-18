from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from seplis_play.utils.sa_base_utils import SABase
from seplis_play.utils.sa_utc_datetime_utils import UtcDateTime


class MMovieIdLookup(SABase):
    __tablename__ = 'movie_id_lookup'

    file_title: Mapped[str] = mapped_column(sa.String(200), primary_key=True)
    movie_title: Mapped[str | None] = mapped_column(sa.String(200))
    movie_id: Mapped[int | None] = mapped_column(sa.Integer)
    updated_at: Mapped[datetime | None] = mapped_column(UtcDateTime)


class MMovie(SABase):
    __tablename__ = 'movies'

    movie_id: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    path: Mapped[str] = mapped_column(sa.String(400), primary_key=True)
    meta_data: Mapped[Any | None] = mapped_column('metadata', sa.JSON)
    modified_time: Mapped[datetime | None] = mapped_column(UtcDateTime)
