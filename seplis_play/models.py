from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from dateutil.parser import parse
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator


class Base(DeclarativeBase):
    pass


class UtcDateTime(TypeDecorator):  # type: ignore
    impl = sa.DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(
        self, value: datetime | str | None, dialect: sa.Dialect
    ) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, str):
            value = parse(value)
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        else:
            value = value.astimezone(UTC)
        return value

    def process_result_value(self, value: Any | str, dialect: Dialect) -> Any:
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=UTC)
            else:
                value = value.astimezone(UTC)
        return value


class Episode(Base):
    __tablename__ = 'episodes'

    series_id: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    number: Mapped[int | None] = mapped_column(sa.Integer)
    path: Mapped[str] = mapped_column(sa.Text, primary_key=True)
    meta_data: Mapped[Any | None] = mapped_column('metadata', sa.JSON)
    modified_time: Mapped[datetime | None] = mapped_column(UtcDateTime)


class EpisodeNumberLookup(Base):
    __tablename__ = 'episode_number_lookup'

    series_id: Mapped[int] = mapped_column(sa.Integer, primary_key=True)
    lookup_type: Mapped[int] = mapped_column(sa.Integer, primary_key=True)
    lookup_value: Mapped[str] = mapped_column(sa.String(45), primary_key=True)
    number: Mapped[int | None] = mapped_column(sa.Integer)


class SeriesIdLookup(Base):
    __tablename__ = 'series_id_lookup'

    file_title: Mapped[str] = mapped_column(sa.String(200), primary_key=True)
    series_title: Mapped[str | None] = mapped_column(sa.String(200))
    series_id: Mapped[int | None] = mapped_column(sa.Integer)
    updated_at: Mapped[datetime | None] = mapped_column(UtcDateTime)


class MovieIdLookup(Base):
    __tablename__ = 'movie_id_lookup'

    file_title: Mapped[str] = mapped_column(sa.String(200), primary_key=True)
    movie_title: Mapped[str | None] = mapped_column(sa.String(200))
    movie_id: Mapped[int | None] = mapped_column(sa.Integer)
    updated_at: Mapped[datetime | None] = mapped_column(UtcDateTime)


class Movie(Base):
    __tablename__ = 'movies'

    movie_id: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    path: Mapped[str] = mapped_column(sa.String(400), primary_key=True)
    meta_data: Mapped[Any | None] = mapped_column('metadata', sa.JSON)
    modified_time: Mapped[datetime | None] = mapped_column(UtcDateTime)


class ExternalSubtitle(Base):
    __tablename__ = 'external_subtitles'

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    path: Mapped[str] = mapped_column(sa.String(1000), nullable=False)
    type: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    language: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    forced: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default='0')
    default: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default='0')
    sdh: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default='0')
