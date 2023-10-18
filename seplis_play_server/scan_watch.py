import asyncio
import os
from watchfiles import awatch, Change
from seplis_play_server.scanners import Movie_scan, Episode_scan, Play_scan, Subtitle_scan
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

            # if the file is being written it will trigger a change event multiple times
            # so we try and wait for the file to be written before parsing it.
            if path in files_waiting_to_finish:
                files_waiting_to_finish[path].cancel()                
            files_waiting_to_finish[path] = asyncio.create_task(parse(
                path=path, 
                change=change,
                scan_info=scan_info,
            ))

    w.cancel()

def get_scanner(scan: ConfigPlayScanModel, type_=None) -> Play_scan:
    if not type_:
        type_ = scan.type
    if type_ == 'series':
        return Episode_scan(
            scan_path=scan.path, 
            make_thumbnails=scan.make_thumbnails,
            parser=scan.parser,
        )
    elif type_ == 'movies':
        return Movie_scan(
            scan_path=scan.path, 
            make_thumbnails=scan.make_thumbnails,
            parser=scan.parser, 
        )
    elif type_ == 'subtitles':
        return Subtitle_scan(
            scan_path=scan.path, 
            make_thumbnails=False,
            parser=scan.parser,
        )


async def worker(queue: asyncio.Queue):
    while True:
        item = await queue.get()
        if item is None:
            break
        change, path, scan_info = item
        try:
            logger.info(f'[Event detected: {change.name}]: {path} ({scan_info.type})')
            scanner = get_scanner(scan_info)
            scanner_subtitles = get_scanner(scan_info, type_='subtitles')
            info = os.path.splitext(path)
            if len(info) == 2 and info[1]:
                if info[1][1:].lower() in config.media_types:
                    s = scanner
                elif info[1][1:].lower() in config.subtitle_types:
                    s = scanner_subtitles
                else:
                    continue
                parsed = s.parse(path)
                if parsed:
                    if change in (Change.added, Change.modified):
                        await s.save_item(parsed, path)
                    elif change == Change.deleted:
                        await s.delete_path(path)
                else:
                    logger.warning(f'Unknown: {path}')
            else:
                # if path is a directory scan it
                if change == Change.added:
                    for s in (scanner, scanner_subtitles):
                        s.scan_path = path
                        await s.scan()
                elif change == Change.deleted:
                    for s in (scanner, scanner_subtitles):
                        paths = await s.get_paths_matching_base_path(path)
                        for path in paths:
                            await s.delete_path(path)
        except Exception as e:
            logger.exception(e)
        
        queue.task_done()


async def parse(path: str, change: Change, scan_info: ConfigPlayScanModel):
    # wait so we don't execute for the same file multiple times within a short time
    # incase the file is being written.
    if change in (Change.added, Change.modified):
        await asyncio.sleep(3)
    files_waiting_to_finish.pop(path, None)
    await scan_queue.put((change, path, scan_info))