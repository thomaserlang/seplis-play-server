import asyncio
import os
from watchfiles import awatch, Change
from seplis_play_server.scanners import Movie_scan, Episode_scan, Play_scan
from seplis_play_server import config, logger
from seplis_play_server.config import ConfigPlayScanModel

files_waiting_to_finish = {}

scan_queue = asyncio.Queue()


async def main():
    w = asyncio.create_task(worker(scan_queue))
    for scan in config.scan:
        logger.info(f'Watching: {scan.path} ({scan.type})')
    async for changes in awatch(*[str(scan.path) for scan in config.scan]):
        for c in changes:
            changed, path = c       
            scan_info = None     
            for scan in config.scan:
                if path.lower().startswith(str(scan.path).lower()):
                    scan_info = scan
                    break
            logger.debug(f'{changed.name}: {path} ({scan_info.type})')
            # if the file is being writtin it will trigger a change event multiple times
            # so we try and wait for the file to be written before parsing it.
            if path in files_waiting_to_finish:
                files_waiting_to_finish[path].cancel()
                files_waiting_to_finish.pop(path)
                
            files_waiting_to_finish[path] = asyncio.create_task(parse(
                path=path, 
                changed=changed,
                scan_info=scan_info,
            ))


def get_scanner(scan: ConfigPlayScanModel) -> Play_scan:
    if scan.type == 'series':
        return Episode_scan(
            scan_path=scan.path, 
            make_thumbnails=scan.make_thumbnails,
            parser=scan.parser,
        )
    elif scan.type == 'movies':
        return Movie_scan(
            scan_path=scan.path, 
            make_thumbnails=scan.make_thumbnails,
            parser=scan.parser, 
        )


async def worker(queue: asyncio.Queue):
    while True:
        item = await queue.get()
        if item is None:
            break
        changed, path, scan_info = item
        scanner = get_scanner(scan_info)
        logger.info(f'{changed.name}: {path} ({scan_info.type})')
        parsed = scanner.parse(path)
        if parsed:
            if changed in (Change.added, Change.modified):
                await scanner.save_item(parsed, path)
            elif changed == Change.deleted:
                await scanner.delete_path(path)
        else:
            logger.warning(f'Unknown: {path}')
        queue.task_done()


async def parse(path: str, changed: Change, scan_info: ConfigPlayScanModel):
    # wait for the file to be fully written
    if changed in (Change.added, Change.modified):
        await asyncio.sleep(3)
    files_waiting_to_finish.pop(path, None)
    info = os.path.splitext(path)
    if len(info) != 2:
        return
    if info[1][1:].lower() in config.media_types:
        await scan_queue.put((changed, path, scan_info))