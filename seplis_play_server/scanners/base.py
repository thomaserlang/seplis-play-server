import os, os.path, subprocess
from datetime import datetime
from seplis_play_server import config, utils, logger

class Play_scan:

    def __init__(self, scan_path: str, type_: str, make_thumbnails: bool = False, cleanup_mode = False):
        if not os.path.exists(scan_path):
            raise Exception(f'scan_path "{scan_path}" does not exist')
        self.scan_path = scan_path
        self.type = type_
        self.make_thumbnails = make_thumbnails
        self.cleanup_mode = cleanup_mode

    async def save_item(self, item, path):
        raise NotImplementedError()

    def parse(self, filename):
        raise NotImplementedError()

    async def delete_item(self, item, path):
        raise NotImplementedError()

    async def scan(self):
        raise NotImplementedError()

    def get_files(self):
        '''
        Looks for files in the `self.scan_path` directory.
        '''
        files = []
        for dirname, dirnames, filenames in os.walk(self.scan_path):
            for file_ in filenames:
                info = os.path.splitext(file_)
                if file_.startswith('._'):
                    continue
                if len(info) != 2:
                    continue
                if info[1][1:].lower() not in config.media_types:
                    continue
                files.append(
                    os.path.join(dirname, file_)
                )
        return files

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
        cmd = [
            ffprobe,
            '-show_streams',
            '-show_format',
            '-loglevel', 'quiet',
            '-print_format', 'json',
            path,
        ]
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        data = process.stdout.read()
        error = process.stderr.read()
        if error:        
            if isinstance(error, bytes):
                error = error.decode('utf-8')   
            raise Exception(f'FFprobe error: {error}')
        if not data:
            return
        if isinstance(data, bytes):
            data = data.decode('utf-8')
        data = utils.json_loads(data)
        return data

    def get_file_modified_time(self, path):
        try:
            return datetime.utcfromtimestamp(
                os.path.getmtime(path)
            ).replace(microsecond=0)
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
            os.path.join(config.ffmpeg_folder, 'ffmpeg'),
            '-vsync', '0',
            '-i', path,
            '-vf', 'fps=1/60,scale=320:-2',
            '-lossless', '0',
            '-compression_level', '6',
            '-vcodec', 'libwebp',
            os.path.join(thumb, '%d.webp')
        ]
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        output, err = process.communicate()
        if process.returncode > 0:
            os.rmdir(thumb)
            logger.error(err)
