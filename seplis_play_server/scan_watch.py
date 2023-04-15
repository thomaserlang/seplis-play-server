import asyncio
import os
from watchfiles import awatch, Change
from seplis_play_server.scanners import Movie_scan, Episode_scan, Play_scan
from seplis_play_server import config, logger


async def main():
    scanners: dict[str, scan.Play_scan] = {}
    for scan in config.scan:
        if scan.type == 'series':
            scanners[scan.path] = Episode_scan(
                scan_path=scan.path, 
                make_thumbnails=scan.make_thumbnails,
                parser=scan.parser,
            )
        elif scan.type == 'movies':
            scanners[scan.path] = Movie_scan(
                scan_path=scan.path, 
                make_thumbnails=scan.make_thumbnails,
                parser=scan.parser, 
            )
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