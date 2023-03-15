import sqlalchemy as sa
from datetime import datetime, timezone

base = sa.orm.declarative_base()


class UtcDateTime(sa.TypeDecorator):
    impl = sa.DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            if not isinstance(value, datetime):
                raise TypeError('expected datetime.datetime, not ' +
                                repr(value))
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            else:
                value = value.astimezone(timezone.utc)
            return value

    def process_result_value(self, value, dialect):
        if value is not None and isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            else:
                value = value.astimezone(timezone.utc)
        return value
    

class Episode(base):
    __tablename__ = 'episodes'

    series_id = sa.Column(sa.Integer, nullable=False)
    number = sa.Column(sa.Integer)
    path = sa.Column(sa.Text, primary_key=True)
    meta_data = sa.Column('metadata', sa.JSON)
    modified_time = sa.Column(UtcDateTime)


class Episode_number_lookup(base):
    __tablename__ = 'episode_number_lookup'    

    series_id = sa.Column(sa.Integer, primary_key=True)
    lookup_type = sa.Column(sa.Integer, primary_key=True)
    lookup_value = sa.Column(sa.String(45), primary_key=True)
    number = sa.Column(sa.Integer)


class Series_id_lookup(base):
    __tablename__ = 'series_id_lookup'

    file_title = sa.Column(sa.String(200), primary_key=True)
    series_title = sa.Column(sa.String(200))
    series_id = sa.Column(sa.Integer)
    updated_at = sa.Column(UtcDateTime)


class Movie_id_lookup(base):
    __tablename__ = 'movie_id_lookup'

    file_title = sa.Column(sa.String(200), primary_key=True)
    movie_title = sa.Column(sa.String(200))
    movie_id = sa.Column(sa.Integer)
    updated_at = sa.Column(UtcDateTime)


class Movie(base):
    __tablename__ = 'movies'

    movie_id = sa.Column(sa.Integer, nullable=False)
    path = sa.Column(sa.String(400), primary_key=True)
    meta_data = sa.Column('metadata', sa.JSON)
    modified_time = sa.Column(UtcDateTime)