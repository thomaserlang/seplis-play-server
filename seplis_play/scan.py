from pathlib import Path

from seplis_play import config, logger
from seplis_play.scanners import (
    EpisodeScan,
    MovieScan,
    SubtitleScan,
    cleanup_episodes,
    cleanup_movies,
    cleanup_subtitles,
)


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


def upgrade_scan_db() -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(Path(__file__).parent / 'alembic.ini')
    cfg.set_main_option('script_location', 'seplis_play:migration')
    cfg.set_main_option('sqlalchemy.url', config.database)
    command.upgrade(cfg, 'head')
