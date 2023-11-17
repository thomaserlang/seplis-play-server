import asyncio
import os, os.path, subprocess
from datetime import datetime, timezone
from seplis_play_server import config, utils, logger

class Play_scan:

    SCANNER_NAME = 'Unnamed scanner'
    SUPPORTED_EXTS = config.media_types
    _cached_paths = {}

    def __init__(self, scan_path: str, make_thumbnails: bool = False, cleanup_mode = False, parser = 'internal'):
        if not os.path.exists(scan_path):
            raise Exception(f'scan_path "{scan_path}" does not exist ({self.SCANNER_NAME})')
        self.scan_path = scan_path
        self.make_thumbnails = make_thumbnails
        self.cleanup_mode = cleanup_mode
        self.parser = parser

    async def save_item(self, item, path):
        raise NotImplementedError()

    def parse(self, filename):
        raise NotImplementedError()

    async def delete_path(self, path):
        raise NotImplementedError()    
    
    async def get_paths_matching_base_path(self, base_path):
        raise NotImplementedError()

    async def scan(self):
        logger.info(f'Scanning: {self.scan_path} ({self.SCANNER_NAME})')
        files = self.get_files()
        for f in files:
            title = self.parse(f)
            if title:
                await self.save_item(title, f)

    def get_files(self):
        files = []
        for dirname, file_ in self._get_files(self.scan_path):
            info = os.path.splitext(file_)
            if file_.startswith('._'):
                continue
            if len(info) != 2:
                continue
            if info[1][1:].lower() not in self.SUPPORTED_EXTS:
                continue
            files.append(
                os.path.join(dirname, file_)
            )
        return files
    
    def _get_files(self, scan_path) -> tuple[str, str]:
        if scan_path in self._cached_paths:
            for r in self._cached_paths[scan_path]:
                yield r
        else:
            self._cached_paths[scan_path] = []
            for dirname, _, filenames in os.walk(scan_path):
                for file_ in filenames:
                    self._cached_paths[scan_path].append((dirname, file_))
                    yield (dirname, file_)

    async def get_metadata(self, path):
        '''
        :returns: dict
            metadata is a `dict` taken from the result of ffprobe.
        '''
        if not os.path.exists(path):
            raise Exception(f'Path "{path}" does not exist')
        ffprobe = os.path.join(config.ffmpeg_folder, 'ffprobe')
        if not os.path.exists(ffprobe):
            raise Exception(f'ffprobe not found in "{config.ffmpeg_folder}"')
        logger.debug(f'Getting metadata from: {path}')
        cmd = [
            '-show_streams',
            '-show_format',
            '-loglevel', 'error',
            '-print_format', 'json',
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
            raise Exception(f'FFprobe error: {error}')
        if not data:
            raise Exception(f'Failed to get metadata from {path}, either this is not a media file or it is corrupt.')
        if isinstance(data, bytes):
            data = data.decode('utf-8')
        data = utils.json_loads(data)
        if config.extract_keyframes and path.endswith('.mkv'):
            data['keyframes'] = await self.get_keyframes(path)
        return data
    

    async def get_keyframes(self, path):
        if not os.path.exists(path):
            raise Exception(f'Path "{path}" does not exist')
        ffprobe = os.path.join(config.ffmpeg_folder, 'ffprobe')
        if not os.path.exists(ffprobe):
            raise Exception(f'ffprobe not found in "{config.ffmpeg_folder}"')
        logger.debug(f'Getting keyframes from: {path}')
        cmd = [
            '-loglevel', 'error',
            '-skip_frame', 'nokey',
            '-show_entries', 'packet=pts_time,flags',
            '-select_streams', 'v',
            '-of', 'json',
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
            logger.error(f'FFprobe error: {error}')
            return
        
        if not data:
            logger.error(f'Failed to get keyframes from {path}, either this is not a media file or it is corrupt.')
            return
        
        if isinstance(data, bytes):
            data = data.decode('utf-8')
        data = utils.json_loads(data)
        keyframes = [r['pts_time'] for r in data['packets'] if r['flags'].startswith('K') and r.get('pts_time')]
        return keyframes


    def get_file_modified_time(self, path):
        try:
            return datetime.utcfromtimestamp(
                os.path.getmtime(path)
            ).replace(microsecond=0, tzinfo=timezone.utc)
        except Exception as e:
            logger.error(str(e))
            

    async def thumbnails(self, key, path):
        thumb = os.path.join(config.thumbnails_path, key)
        if os.path.exists(thumb):
            logger.debug(f'[{key}] Thumbnails already created: {thumb}')
            return
        os.mkdir(thumb)
        logger.info(f'[{key}] Creating thumbnails')
        cmd = [
            '-vsync', '0',
            '-i', path,
            '-vf', 'fps=1/60,scale=320:-2',
            '-lossless', '0',
            '-compression_level', '6',
            '-vcodec', 'libwebp',
            os.path.join(thumb, '%d.webp')
        ]
        process = await asyncio.create_subprocess_exec(
            os.path.join(config.ffmpeg_folder, 'ffmpeg'),
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        output, err = await process.communicate()
        if process.returncode > 0:
            os.rmdir(thumb)
            logger.error(err)
