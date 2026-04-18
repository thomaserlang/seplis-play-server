import os
from datetime import UTC, datetime

import sqlalchemy as sa

from seplis_play import client, config, database, logger

from .movie_models import MMovie
from .movie_schemas import PlayServerMovieCreate


async def cleanup_movies() -> None:
    logger.info('Cleanup movies started')
    movies: list[PlayServerMovieCreate] = []
    async with database.session() as session:
        rows = await session.scalars(sa.select(MMovie))
        deleted_count = 0
        for m in rows:
            logger.debug(f'Checking if exists: {m.path}')
            if os.path.exists(m.path):
                movies.append(
                    PlayServerMovieCreate(
                        movie_id=m.movie_id,
                        created_at=m.modified_time or datetime.now(tz=UTC),
                    )
                )
                continue
            deleted_count += 1
            await session.execute(
                sa.delete(MMovie).where(
                    MMovie.movie_id == m.movie_id,
                    MMovie.path == m.path,
                )
            )
        await session.commit()
        logger.info(f'{deleted_count} movies was deleted from the database')

        if not config.server_id:
            logger.warning('No server_id specified movies not sent to play server index')
        else:
            r = await client.put(
                f'/2/play-servers/{config.server_id}/movies',
                json=[r.model_dump(mode='json') for r in movies],
                headers={
                    'Authorization': f'Secret {config.secret}',
                    'Content-Type': 'application/json',
                },
                timeout=900,
            )
            if r.status_code >= 400:
                logger.error(
                    f'Failed to add {len(movies)} movies to the movie play '
                    f'server index ({config.server_id}): {r.content}'
                )
            else:
                logger.info(
                    f'Updated the movie play server index with {len(movies)} '
                    f'movies ({config.server_id})'
                )
