import jwt
from sqlalchemy import select
from fastapi import HTTPException
from seplis_play_server import database, models
from seplis_play_server import config


async def get_metadata(play_id) -> list[dict]:
    data = decode_play_id(play_id)
    if data['type'] == 'series':
        query = select(models.Episode.meta_data).where(
            models.Episode.series_id == data['series_id'],
            models.Episode.number == data['number'],
        )
    elif data['type'] == 'movie':
        query = select(models.Movie.meta_data).where(
            models.Movie.movie_id == data['movie_id'],
        )
    async with database.session() as session:
        r = await session.scalars(query)
        return r.all()


def decode_play_id(play_id: str) -> list[dict]:
    try:
        data = jwt.decode(
            play_id,
            config.secret,
            algorithms=['HS256'],
        )
        return data
    except Exception as e:
        raise HTTPException(400, 'Play id invalid')