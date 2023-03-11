import click, asyncio
import uvicorn
from seplis_play_server import config
from seplis_play_server.logger import set_logger


@click.group()
@click.option('--log_path', '-lp', default=None, help='a folder to store the log files in')
@click.option('--log_level', '-ll', default=None, help='notset, debug, info, warning, error or critical')
def cli(log_path, log_level):
    if log_path != None:
        config.logging.path = log_path
    if log_level:
        config.logging.level = log_level


@cli.command()
def run():
    uvicorn.run('seplis_play_server.main:app', host='0.0.0.0', port=config.port, reload=config.debug, proxy_headers=True, forwarded_allow_ips='*')


async def play_scan_task(task):
    from seplis_play_server.database import database
    import seplis_play_server.scan
    seplis_play_server.scan.upgrade_scan_db()
    database.setup()
    try:
        await task
    finally:
        await database.close()


@cli.command()
@click.option('--disable-cleanup', is_flag=True, help='Disable cleanup after scan')
@click.option('--disable-thumbnails', is_flag=True, help='Disable making thumbnails')
def scan(disable_cleanup, disable_thumbnails):
    set_logger('play_scan.log')
    import seplis_play_server.scan
    asyncio.run(play_scan_task(seplis_play_server.scan.scan(
        disable_cleanup=disable_cleanup,
        disable_thumbnails=disable_thumbnails,
    )))


@cli.command()
def scan_watch():
    set_logger('play_scan_watch.log')
    import seplis_play_server.scan_watch
    asyncio.run(play_scan_task(seplis_play_server.scan_watch.main()))


@cli.command()
def scan_cleanup():
    set_logger('play_scan_cleanup.log')
    import seplis_play_server.scan
    asyncio.run(play_scan_task(seplis_play_server.scan.cleanup()))


def main():
    cli()


if __name__ == "__main__":
    main()