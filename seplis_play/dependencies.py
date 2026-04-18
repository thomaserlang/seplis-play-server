from typing import Any

import jwt
from fastapi import HTTPException
from sqlalchemy import select

from seplis_play import config, database, logger
from seplis_play.scanners.episode.episode_models import MEpisode
from seplis_play.scanners.movie.movie_models import MMovie
from seplis_play.schemas.page_id_schema import PlayId


async def get_sources(play_id: str) -> list[dict[str, Any]]:
    data = decode_play_id(play_id)
    if data.type == 'series':
        query = select(MEpisode.meta_data).where(
            MEpisode.series_id == data.series_id,
            MEpisode.number == data.number,
        )
    elif data.type == 'movie':
        query = select(MMovie.meta_data).where(
            MMovie.movie_id == data.movie_id,
        )
    else:
        raise HTTPException(400, 'Play id type not supported')
    async with database.session() as session:
        r = await session.scalars(query)
        return [d for d in r if d]


async def get_metadata(play_id: str, source_index: int) -> dict[str, Any]:
    metadatas = await get_sources(play_id)
    if source_index > (len(metadatas) - 1):
        raise HTTPException(404, 'No metadata')
    return metadatas[source_index]


def decode_play_id(play_id: str) -> PlayId:
    try:
        data = jwt.decode(
            play_id,
            config.secret,
            algorithms=['HS256'],
        )
        return PlayId.model_validate(data)
    except jwt.PyJWTError as e:
        logger.error(f'Failed to decode play id: {e}')
        raise HTTPException(400, 'Play id invalid') from e
