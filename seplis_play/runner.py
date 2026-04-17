import asyncio
import os
from collections.abc import Awaitable
from typing import Any

import click
import uvicorn

from seplis_play import config


@click.group()
def cli() -> None:
    pass


@cli.command()
def run() -> None:
    if config.transcode_folder:
        os.makedirs(config.transcode_folder, exist_ok=True)

    uvicorn.run(
        'seplis_play.main:app',
        host='0.0.0.0',
        port=config.port,
        reload=config.debug,
        proxy_headers=True,
        forwarded_allow_ips='*',
    )


async def play_scan_task(task: Awaitable[Any]) -> None:
    import seplis_play.scan
    from seplis_play.database import database

    seplis_play.scan.upgrade_scan_db()
    database.setup()
    try:
        await task
    finally:
        await database.close()


@cli.command()
@click.option('--disable-cleanup', is_flag=True, help='Disable cleanup after scan')
@click.option('--disable-thumbnails', is_flag=True, help='Disable making thumbnails')
def scan(disable_cleanup: bool, disable_thumbnails: bool) -> None:
    import seplis_play.scan

    asyncio.run(
        play_scan_task(
            seplis_play.scan.scan(
                disable_cleanup=disable_cleanup,
                disable_thumbnails=disable_thumbnails,
            )
        )
    )


@cli.command()
def scan_watch() -> None:
    import seplis_play.scan_watch

    asyncio.run(play_scan_task(seplis_play.scan_watch.main()))


@cli.command()
def scan_cleanup() -> None:
    import seplis_play.scan

    asyncio.run(play_scan_task(seplis_play.scan.cleanup()))


def main() -> None:
    cli()


if __name__ == '__main__':
    main()
