import os

import sqlalchemy as sa

from seplis_play import database, logger

from .subtitle_models import MExternalSubtitle


async def cleanup_subtitles() -> None:
    logger.info('Cleanup subtitles started')
    async with database.session() as session:
        rows = await session.scalars(sa.select(MExternalSubtitle))
        deleted_count = 0
        for s in rows:
            logger.debug(f'Checking if exists: {s.path}')
            if os.path.exists(s.path):
                continue
            deleted_count += 1
            await session.execute(
                sa.delete(MExternalSubtitle).where(
                    MExternalSubtitle.path == s.path,
                )
            )
        await session.commit()
        logger.info(f'{deleted_count} subtitles was deleted from the database')
