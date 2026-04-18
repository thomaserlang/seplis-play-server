import os
from datetime import UTC, datetime

import sqlalchemy as sa

from seplis_play import client, config, database, logger

from .episode_models import MEpisode
from .episode_schemas import PlayServerEpisodeCreate


async def cleanup_episodes() -> None:
    logger.info('Cleanup episodes started')
    episodes: list[PlayServerEpisodeCreate] = []
    async with database.session() as session:
        deleted_count = 0
        rows = await session.scalars(sa.select(MEpisode))
        for e in rows:
            logger.debug(f'Checking if exists: {e.path}')
            if os.path.exists(e.path):
                episodes.append(
                    PlayServerEpisodeCreate(
                        series_id=e.series_id,
                        episode_number=e.number or 0,
                        created_at=e.modified_time or datetime.now(tz=UTC),
                    )
                )
                continue
            deleted_count += 1
            await session.execute(
                sa.delete(MEpisode).where(
                    MEpisode.series_id == e.series_id,
                    MEpisode.number == e.number,
                    MEpisode.path == e.path,
                )
            )
        await session.commit()
        logger.info(f'{deleted_count} episodes were deleted from the database')

        if not config.server_id:
            logger.warning(
                'No server_id specified episodes not sent to play server index'
            )
        else:
            r = await client.put(  # noqa: F821
                f'/2/play-servers/{config.server_id}/episodes',
                json=[r.model_dump(mode='json') for r in episodes],
                headers={
                    'Authorization': f'Secret {config.secret}',
                    'Content-Type': 'application/json',
                },
                timeout=900,
            )
            if r.status_code >= 400:
                logger.error(
                    f'Failed to add {len(episodes)} episodes to the episode '
                    f'play server index ({config.server_id}): {r.content}'
                )
            else:
                logger.info(
                    f'Updated {len(episodes)} episodes to the episode play '
                    f'server index ({config.server_id})'
                )
