from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from seplis_play.utils.sa_base_utils import SABase
from seplis_play.utils.sa_utc_datetime_utils import UtcDateTime


class MSeriesIdLookup(SABase):
    __tablename__ = 'series_id_lookup'

    file_title: Mapped[str] = mapped_column(sa.String(200), primary_key=True)
    series_title: Mapped[str | None] = mapped_column(sa.String(200))
    series_id: Mapped[int | None] = mapped_column(sa.Integer)
    updated_at: Mapped[datetime | None] = mapped_column(UtcDateTime)


class MEpisode(SABase):
    __tablename__ = 'episodes'

    series_id: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    number: Mapped[int | None] = mapped_column(sa.Integer)
    path: Mapped[str] = mapped_column(sa.Text, primary_key=True)
    meta_data: Mapped[Any | None] = mapped_column('metadata', sa.JSON)
    modified_time: Mapped[datetime | None] = mapped_column(UtcDateTime)


class MEpisodeNumberLookup(SABase):
    __tablename__ = 'episode_number_lookup'

    series_id: Mapped[int] = mapped_column(sa.Integer, primary_key=True)
    lookup_type: Mapped[int] = mapped_column(sa.Integer, primary_key=True)
    lookup_value: Mapped[str] = mapped_column(sa.String(45), primary_key=True)
    number: Mapped[int | None] = mapped_column(sa.Integer)
