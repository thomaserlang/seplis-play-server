import asyncio
import os
import os.path
import subprocess
from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any

from seplis_play import config, logger
from seplis_play.utils.json_utils import json_loads


class PlayScan:
    SCANNER_NAME: str = 'Unnamed scanner'
    SUPPORTED_EXTS: list[str] = config.media_types
    _cached_paths: dict[str, list[tuple[str, str]]] = {}

    def __init__(
        self,
        scan_path: str,
        make_thumbnails: bool = False,
        cleanup_mode: bool = False,
        parser: str = 'internal',
    ) -> None:
        if not os.path.exists(scan_path):
            raise Exception(
                f'scan_path "{scan_path}" does not exist ({self.SCANNER_NAME})'
            )
        self.scan_path = scan_path
        self.make_thumbnails = make_thumbnails
        self.cleanup_mode = cleanup_mode
        self.parser = parser

    async def save_item(self, item: Any, path: str) -> bool:
        raise NotImplementedError()

    def parse(self, filename: str) -> Any:
        raise NotImplementedError()

    async def delete_path(self, path: str) -> bool:
        raise NotImplementedError()

    async def get_paths_matching_base_path(self, base_path: str) -> Any:
        raise NotImplementedError()

    async def scan(self) -> None:
        logger.info(f'Scanning: {self.scan_path} ({self.SCANNER_NAME})')
        files = self.get_files()
        for f in files:
            title = self.parse(f)
            if title:
                await self.save_item(title, f)

    def get_files(self) -> list[str]:
        files: list[str] = []
        for dirname, file_ in self._get_files(self.scan_path):
            info = os.path.splitext(file_)
            if file_.startswith('._'):
                continue
            if len(info) != 2:
                continue
            if info[1][1:].lower() not in self.SUPPORTED_EXTS:
                continue
            files.append(os.path.join(dirname, file_))
        return sorted(files)

    def _get_files(self, scan_path: str) -> Generator[tuple[str, str]]:
        if scan_path in self._cached_paths:
            yield from self._cached_paths[scan_path]
        else:
            self._cached_paths[scan_path] = []
            for dirname, _, filenames in os.walk(scan_path):
                for file_ in filenames:
                    self._cached_paths[scan_path].append((dirname, file_))
                    yield (dirname, file_)

    async def get_metadata(self, path: str) -> dict[str, Any]:
        """
        :returns: dict
            metadata is a `dict` taken from the result of ffprobe.
        """
        if not os.path.exists(path):
            raise Exception(f'Path "{path}" does not exist')
        ffprobe = os.path.join(config.ffmpeg_folder, 'ffprobe')
        if not os.path.exists(ffprobe):
            raise Exception(f'ffprobe not found in "{config.ffmpeg_folder}"')
        logger.debug(f'Getting metadata from: {path}')
        cmd = [
            '-show_streams',
            '-show_format',
            '-loglevel',
            'error',
            '-print_format',
            'json',
            path,
        ]
        process = await asyncio.create_subprocess_exec(
            ffprobe,
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        data, error = await process.communicate()
        if error:
            if isinstance(error, bytes):
                error = error.decode('utf-8')
            raise Exception(f'FFprobe error {path}: {error}')
        if not data:
            raise Exception(
                f'Failed to get metadata from {path}, either this is '
                'not a media file or it is corrupt.'
            )
        if isinstance(data, bytes):
            data = data.decode('utf-8')
        result: dict[str, Any] = json_loads(data)
        if config.extract_keyframes and path.endswith('.mkv'):
            result['keyframes'] = await self.get_keyframes(path)
        return result

    async def get_keyframes(self, path: str) -> list[str] | None:
        if not os.path.exists(path):
            raise Exception(f'Path "{path}" does not exist')
        ffprobe = os.path.join(config.ffmpeg_folder, 'ffprobe')
        if not os.path.exists(ffprobe):
            raise Exception(f'ffprobe not found in "{config.ffmpeg_folder}"')
        logger.debug(f'Getting keyframes from: {path}')
        cmd = [
            '-fflags',
            '+genpts',
            '-v',
            'error',
            '-skip_frame',
            'nokey',
            '-show_entries',
            'packet=pts_time,flags',
            '-select_streams',
            'v',
            '-of',
            'json',
            path,
        ]
        process = await asyncio.create_subprocess_exec(
            ffprobe,
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        data, error = await process.communicate()

        if error:
            if isinstance(error, bytes):
                error = error.decode('utf-8')
            logger.error(f'FFprobe error {path}:  {error}')
            return None

        if not data:
            logger.error(
                f'Failed to get keyframes from {path}, either this is '
                'not a media file or it is corrupt.'
            )
            return None

        if isinstance(data, bytes):
            data = data.decode('utf-8')
        parsed: dict[str, Any] = json_loads(data)
        keyframes: list[str] = [
            r['pts_time']
            for r in parsed['packets']
            if r['flags'].startswith('K_') and r.get('pts_time')
        ]
        return keyframes

    def get_file_modified_time(self, path: str) -> datetime | None:
        try:
            return datetime.fromtimestamp(os.path.getmtime(path), tz=UTC).replace(
                microsecond=0
            )
        except Exception as e:
            logger.error(str(e))
            return None

    async def thumbnails(self, key: str, path: str) -> None:
        if config.thumbnails_path is None:
            raise Exception('thumbnails_path is not configured')
        thumb = os.path.join(config.thumbnails_path, key)
        if os.path.exists(thumb):
            logger.debug(f'[{key}] Thumbnails already created: {thumb}')
            return
        os.mkdir(thumb)
        logger.info(f'[{key}] Creating thumbnails')
        cmd = [
            '-vsync',
            '0',
            '-i',
            path,
            '-vf',
            'fps=1/60,scale=320:-2',
            '-lossless',
            '0',
            '-compression_level',
            '6',
            '-vcodec',
            'libwebp',
            os.path.join(thumb, '%d.webp'),
        ]
        process = await asyncio.create_subprocess_exec(
            os.path.join(config.ffmpeg_folder, 'ffmpeg'),
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        _, err = await process.communicate()
        if process.returncode and process.returncode > 0:
            os.rmdir(thumb)
            logger.error(err)
