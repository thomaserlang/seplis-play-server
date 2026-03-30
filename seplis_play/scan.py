import os
import os.path
from datetime import UTC, datetime
from pathlib import Path

import sqlalchemy as sa

from seplis_play import config, logger, models, schemas
from seplis_play.client import client
from seplis_play.database import database

from .scanners import EpisodeScan, MovieScan, SubtitleScan


async def scan(disable_cleanup: bool = False, disable_thumbnails: bool = False) -> None:
    for s in config.scan:
        scanner: EpisodeScan | MovieScan | None = None
        if s.type == 'series':
            scanner = EpisodeScan(
                scan_path=str(s.path),
                make_thumbnails=s.make_thumbnails and not disable_thumbnails,
                cleanup_mode=not disable_cleanup,
                parser=s.parser,
            )
        elif s.type == 'movies':
            scanner = MovieScan(
                scan_path=str(s.path),
                make_thumbnails=s.make_thumbnails and not disable_thumbnails,
                cleanup_mode=not disable_cleanup,
                parser=s.parser,
            )
        subtitles_scanner = SubtitleScan(
            scan_path=str(s.path),
            make_thumbnails=False,
            parser=s.parser,
        )
        if scanner:
            await scanner.scan()
            await subtitles_scanner.scan()
        else:
            logger.error(f'Scan type: "{s.type}" is not supported')

    if not disable_cleanup:
        await cleanup()


async def cleanup() -> None:
    logger.info('Cleanup started')
    await cleanup_episodes()
    await cleanup_movies()
    await cleanup_subtitles()


async def cleanup_episodes() -> None:
    logger.info('Cleanup episodes started')
    episodes: list[schemas.PlayServerEpisodeCreate] = []
    async with database.session() as session:
        deleted_count = 0
        rows = await session.scalars(sa.select(models.Episode))
        for e in rows:
            logger.debug(f'Checking if exists: {e.path}')
            if os.path.exists(e.path):
                episodes.append(
                    schemas.PlayServerEpisodeCreate(
                        series_id=e.series_id,
                        episode_number=e.number or 0,
                        created_at=e.modified_time or datetime.now(tz=UTC),
                    )
                )
                continue
            deleted_count += 1
            await session.execute(
                sa.delete(models.Episode).where(
                    models.Episode.series_id == e.series_id,
                    models.Episode.number == e.number,
                    models.Episode.path == e.path,
                )
            )
        await session.commit()
        logger.info(f'{deleted_count} episodes were deleted from the database')

        if not config.server_id:
            logger.warning(
                'No server_id specified episodes not sent to play server index'
            )
        else:
            r = await client.put(
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


async def cleanup_movies() -> None:
    logger.info('Cleanup movies started')
    movies: list[schemas.PlayServerMovieCreate] = []
    async with database.session() as session:
        rows = await session.scalars(sa.select(models.Movie))
        deleted_count = 0
        for m in rows:
            logger.debug(f'Checking if exists: {m.path}')
            if os.path.exists(m.path):
                movies.append(
                    schemas.PlayServerMovieCreate(
                        movie_id=m.movie_id,
                        created_at=m.modified_time or datetime.now(tz=UTC),
                    )
                )
                continue
            deleted_count += 1
            await session.execute(
                sa.delete(models.Movie).where(
                    models.Movie.movie_id == m.movie_id,
                    models.Movie.path == m.path,
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


async def cleanup_subtitles() -> None:
    logger.info('Cleanup subtitles started')
    async with database.session() as session:
        rows = await session.scalars(sa.select(models.ExternalSubtitle))
        deleted_count = 0
        for s in rows:
            logger.debug(f'Checking if exists: {s.path}')
            if os.path.exists(s.path):
                continue
            deleted_count += 1
            await session.execute(
                sa.delete(models.ExternalSubtitle).where(
                    models.ExternalSubtitle.path == s.path,
                )
            )
        await session.commit()
        logger.info(f'{deleted_count} subtitles was deleted from the database')


def upgrade_scan_db() -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(Path(__file__).parent / 'alembic.ini')
    cfg.set_main_option('script_location', 'seplis_play:migration')
    cfg.set_main_option('sqlalchemy.url', config.database)
    command.upgrade(cfg, 'head')
