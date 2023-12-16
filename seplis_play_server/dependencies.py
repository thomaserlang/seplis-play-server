import jwt
from sqlalchemy import select
from fastapi import HTTPException
from seplis_play_server import database, logger, models, schemas
from seplis_play_server import config

async def get_sources(play_id: str):
    data = decode_play_id(play_id)
    if data.type == 'series':
        query = select(models.Episode.meta_data).where(
            models.Episode.series_id == data.series_id,
            models.Episode.number == data.number,
        )
    elif data.type == 'movie':
        query = select(models.Movie.meta_data).where(
            models.Movie.movie_id == data.movie_id,
        )
    else:
        raise HTTPException(400, 'Play id type not supported')
    async with database.session() as session:
        r = await session.scalars(query)
        return list(r.all())
    

async def get_metadata(play_id: str, source_index: int) -> list[dict]:
    metadatas = await get_sources(play_id)
    if source_index > (len(metadatas) - 1):
        raise HTTPException(404, 'No metadata')
    return metadatas[source_index]


def decode_play_id(play_id: str):
    try:
        data = jwt.decode(
            play_id,
            config.secret,
            algorithms=['HS256'],
        )
        return schemas.Play_id.model_validate(data)
    except jwt.PyJWTError as e:
        logger.error(f'Failed to decode play id: {e}')
        raise HTTPException(400, 'Play id invalid')