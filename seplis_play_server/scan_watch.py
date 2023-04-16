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
            change, path = c       
            scan_info = None     
            for scan in config.scan:
                if path.lower().startswith(str(scan.path).lower()):
                    scan_info = scan
                    break
            # if the file is being writtin it will trigger a change event multiple times
            # so we try and wait for the file to be written before parsing it.
            if path in files_waiting_to_finish:
                files_waiting_to_finish[path].cancel()
                files_waiting_to_finish.pop(path)
                
            files_waiting_to_finish[path] = asyncio.create_task(parse(
                path=path, 
                change=change,
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
        change, path, scan_info = item

        logger.info(f'{change.name}: {path} ({scan_info.type})')
        scanner = get_scanner(scan_info)
        info = os.path.splitext(path)
        if len(info) == 2:
            if info[1][1:].lower() not in config.media_types:
                continue
            parsed = scanner.parse(path)
            if parsed:
                if change in (Change.added, Change.modified):
                    await scanner.save_item(parsed, path)
                elif change == Change.deleted:
                    await scanner.delete_path(path)
            else:
                logger.warning(f'Unknown: {path}')

        else:
            # if path is a directory scan it
            if change == Change.added:
                scanner.scan_path = path
                await scanner.scan()
            elif change == Change.deleted:
                paths = await scanner.get_paths_matching_base_path(path)
                for path in paths:
                    await scanner.delete_path(path)
        
        queue.task_done()


async def parse(path: str, change: Change, scan_info: ConfigPlayScanModel):
    # wait so we don't execute for the same file multiple times within a short time
    # in case the file is being written.
    if change in (Change.added, Change.modified):
        await asyncio.sleep(3)
    files_waiting_to_finish.pop(path, None)
    await scan_queue.put((change, path, scan_info))