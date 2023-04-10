from datetime import datetime, timezone
import os, os.path
import sqlalchemy as sa
from seplis_play_server import config, utils, logger, models, schemas
from seplis_play_server.client import client
from seplis_play_server.database import database


from .scanners import Movie_scan, Episode_scan


async def scan(disable_cleanup=False, disable_thumbnails=False):
    for s in config.scan:
        scanner = None
        if s.type == 'series':
            scanner = Episode_scan(
                scan_path=s.path, 
                make_thumbnails=s.make_thumbnails and not disable_thumbnails,
                cleanup_mode=not disable_cleanup,
            )
        elif s.type == 'movies':
            scanner = Movie_scan(
                scan_path=s.path, 
                make_thumbnails=s.make_thumbnails and not disable_thumbnails,
                cleanup_mode=not disable_cleanup,    
            )
        if scanner:
            await scanner.scan()
        else:
            logger.error(f'Scan type: "{s.type}" is not supported')

    if not disable_cleanup:
        await cleanup()


async def cleanup():
    logger.info('Cleanup started')
    await cleanup_episodes()
    await cleanup_movies()


async def cleanup_episodes():
    episodes: list[schemas.Play_server_episode_create] = []
    async with database.session() as session:
        deleted_count = 0
        logger.info('Getting episodes')
        rows = await session.scalars(sa.select(models.Episode))
        logger.info(f'Found {len(rows)} episodes')
        for e in rows:
            logger.info(f'Checking {e.path}')
            if os.path.exists(e.path):
                episodes.append(schemas.Play_server_episode_create(
                    series_id=e.series_id,
                    episode_number=e.number,
                    created_at=e.modified_time or datetime.now(tz=timezone.utc)
                ))
                continue
            deleted_count += 1
            await session.execute(sa.delete(models.Episode).where(
                models.Episode.series_id == e.series_id,
                models.Episode.number == e.number,
                models.Episode.path == e.path,
            ))
        await session.commit()
        logger.info(f'{deleted_count} episodes was deleted from the database')

        if not config.server_id:
            logger.warn(f'No server_id specified episodes not sent to play server index')
        else:
            r = await client.put(f'/2/play-servers/{config.server_id}/episodes', 
                data=utils.json_dumps(episodes),
                headers={
                    'Authorization': f'Secret {config.secret}',
                    'Content-Type': 'application/json',
                },
                timeout=900,
            )
            if r.status_code >= 400:
                logger.error(f'Faild to add {len(episodes)} episodes to the episode play server index ({config.server_id}): {r.content}')
            else:
                logger.info(f'Updated {len(episodes)} episodes to the episode play server index ({config.server_id})')


async def cleanup_movies():
    movies: list[schemas.Play_server_movie_create] = []
    async with database.session() as session:
        rows = await session.scalars(sa.select(models.Movie))
        deleted_count = 0
        for m in rows:
            if os.path.exists(m.path):
                movies.append(schemas.Play_server_movie_create(
                    movie_id=m.movie_id,
                    created_at=m.modified_time or datetime.now(tz=timezone.utc)
                ))
                continue
            deleted_count += 1
            await session.execute(sa.delete(models.Movie).where(
                models.Movie.movie_id == m.movie_id,
                models.Movie.path == m.path,
            ))
        await session.commit()
        logger.info(f'{deleted_count} movies was deleted from the database')

        if not config.server_id:
            logger.warn(f'No server_id specified movies not sent to play server index')
        else:
            r = await client.put(f'/2/play-servers/{config.server_id}/movies', 
                data=utils.json_dumps(movies),
                headers={
                    'Authorization': f'Secret {config.secret}',
                    'Content-Type': 'application/json',
                },
                timeout=900,
            )
            if r.status_code >= 400:
                logger.error(f'Faild to add {len(movies)} movies to the movie play server index ({config.server_id}): {r.content}')
            else:
                logger.info(f'Updated the movie play server index with {len(movies)} movies ({config.server_id})')


def upgrade_scan_db():
    import alembic.config
    from alembic import command
    cfg = alembic.config.Config(
        os.path.dirname(
            os.path.abspath(__file__)
        )+'/alembic.ini'
    )
    cfg.set_main_option('script_location', 'seplis_play_server:migration')
    cfg.set_main_option('url', config.database)
    command.upgrade(cfg, 'head')