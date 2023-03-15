import asyncio
import os
from watchfiles import awatch, Change
from seplis_play_server.scanners import Movie_scan, Episode_scan, Play_scan
from seplis_play_server import config, logger


async def main():
    scanners: dict[str, scan.Play_scan] = {}
    for scan in config.scan:
        scanners[scan.path] = get_scanner(type_=scan.type, scan_path=scan.path, make_thumbnails=scan.make_thumbnails)
    waiting = {}
    async for changes in awatch(*[str(scan.path) for scan in config.scan]):
        scanner: scan.Play_scan = None
        for c in changes:
            changed, path = c
            for base_path in scanners:
                if path.lower().startswith(str(base_path).lower()):
                    scanner = scanners[base_path]
                    break
            if path in waiting:
                waiting[path].cancel()
                waiting.pop(path)
                
            waiting[path] = asyncio.create_task(parse( 
                scanner=scanner, 
                path=path, 
                changed=changed, 
                waiting=waiting
            ))


def get_scanner(type_: str, scan_path: str, make_thumbnails: bool) -> Play_scan:
    if type_ == 'series':
        return Episode_scan(scan_path=scan_path, make_thumbnails=make_thumbnails)
    elif type_ == 'movies':
        return Movie_scan(scan_path=scan_path, make_thumbnails=make_thumbnails)


async def parse(scanner: Play_scan, path: str, changed: Change, waiting: dict):
    if changed in (Change.added, Change.modified):
        await asyncio.sleep(3)
    waiting.pop(path, None)
    info = os.path.splitext(path)
    if len(info) != 2:
        return
    if info[1][1:].lower() not in config.media_types:
        return
    parsed = scanner.parse(path)
    if parsed:
        if changed in (Change.added, Change.modified):
            logger.info(f'Added/changed: {path}')
            await scanner.save_item(parsed, path)
        elif changed == Change.deleted:
            logger.info(f'Deleted: {path}')
            await scanner.delete_path(path)