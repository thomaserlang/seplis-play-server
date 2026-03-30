from __future__ import annotations

import asyncio
import os
from typing import Literal

from watchfiles import Change, awatch

from seplis_play import config, logger
from seplis_play.config import ConfigPlayScanModel
from seplis_play.scanners import EpisodeScan, MovieScan, PlayScan, SubtitleScan

files_waiting_to_finish: dict[str, asyncio.Task[None]] = {}

scan_queue: asyncio.Queue[tuple[Change, str, ConfigPlayScanModel] | None] = (
    asyncio.Queue()
)


async def main() -> None:
    w: asyncio.Task[None] = asyncio.create_task(worker(scan_queue))
    for scan in config.scan:
        logger.info(f'Watching: {scan.path} ({scan.type})')
    async for changes in awatch(*[str(scan.path) for scan in config.scan]):
        for c in changes:
            change, path = c
            scan_info: ConfigPlayScanModel | None = None
            for scan in config.scan:
                if path.lower().startswith(str(scan.path).lower()):
                    scan_info = scan
                    break
            if not scan_info:
                continue

            # if the file is being written it will trigger a change event multiple times
            # so we try and wait for the file to be written before parsing it.
            if path in files_waiting_to_finish:
                files_waiting_to_finish[path].cancel()
            files_waiting_to_finish[path] = asyncio.create_task(
                parse(
                    path=path,
                    change=change,
                    scan_info=scan_info,
                )
            )

    w.cancel()


def get_scanner(
    scan: ConfigPlayScanModel,
    type_: Literal['series', 'movies', 'subtitles'] | None = None,
) -> PlayScan:
    effective_type = type_ if type_ is not None else scan.type
    if effective_type == 'series':
        return EpisodeScan(
            scan_path=str(scan.path),
            make_thumbnails=scan.make_thumbnails,
            parser=scan.parser,
        )
    if effective_type == 'movies':
        return MovieScan(
            scan_path=str(scan.path),
            make_thumbnails=scan.make_thumbnails,
            parser=scan.parser,
        )
    if effective_type == 'subtitles':
        return SubtitleScan(
            scan_path=str(scan.path),
            make_thumbnails=False,
            parser=scan.parser,
        )
    raise ValueError(f'Unknown scan type: {effective_type!r}')


async def worker(
    queue: asyncio.Queue[tuple[Change, str, ConfigPlayScanModel] | None],
) -> None:
    while True:
        item = await queue.get()
        if item is None:
            break
        change, path, scan_info = item
        try:
            logger.info(f'[Event detected: {change.name}]: {path} ({scan_info.type})')
            info = os.path.splitext(path)
            if len(info) == 2 and info[1]:
                s: PlayScan
                if info[1][1:].lower() in config.media_types:
                    s = get_scanner(scan_info)
                elif info[1][1:].lower() in config.subtitle_types:
                    s = get_scanner(scan_info, type_='subtitles')
                else:
                    continue
                if change in (Change.added, Change.modified):
                    parsed = s.parse(path)
                    if parsed:
                        await s.save_item(parsed, path)
                elif change == Change.deleted:
                    await s.delete_path(path)
                else:
                    logger.warning(f'Unknown: {path}')
            else:
                scanner = get_scanner(scan_info)
                scanner_subtitles = get_scanner(scan_info, type_='subtitles')
                # if path is a directory scan it
                if change == Change.added:
                    for s in (scanner, scanner_subtitles):
                        s.scan_path = path
                        await s.scan()
                elif change == Change.deleted:
                    for s in (scanner, scanner_subtitles):
                        dir_paths = await s.get_paths_matching_base_path(path)
                        for dir_path in dir_paths:
                            await s.delete_path(dir_path)
        except Exception as e:
            logger.exception(e)

        queue.task_done()


async def parse(path: str, change: Change, scan_info: ConfigPlayScanModel) -> None:
    # wait so we don't execute for the same file multiple times within a short time
    # incase the file is being written.
    if change in (Change.added, Change.modified):
        await asyncio.sleep(3)
    files_waiting_to_finish.pop(path, None)
    await scan_queue.put((change, path, scan_info))
