import os, pathlib
from typing import Literal
from pydantic import BaseModel, BaseSettings, AnyHttpUrl
import yaml, tempfile


class ConfigLoggingModel(BaseModel):
    level: Literal['notset', 'debug', 'info', 'warn', 'error', 'critical'] = 'info'
    path: pathlib.Path | None
    max_size: int = 100 * 1000 * 1000 # ~ 95 mb
    num_backups = 10


class ConfigPlayScanModel(BaseModel):
    type: Literal['series', 'movies']
    path: pathlib.Path
    make_thumbnails: bool = False

    
class ConfigModel(BaseSettings):
    debug = False
    test = False
    database: str
    secret: str
    scan: list[ConfigPlayScanModel]
    media_types: list[str] = ['mp4', 'mkv', 'avi', 'mpg']
    
    ffmpeg_folder: pathlib.Path = '/bin'
    ffmpeg_loglevel = '8'
    ffmpeg_logfile: pathlib.Path | None
    ffmpeg_preset: Literal['veryslow', 'slower', 'slow', 'medium', 'fast', 'faster', 'veryfast', 'superfast', 'ultrafast'] = 'veryfast' 
    ffmpeg_hwaccel_enabled = False
    ffmpeg_hwaccel_device: str = '/dev/dri/renderD128'
    ffmpeg_hwaccel: str = 'qsv'
    ffmpeg_hwaccel_low_powermode = True
    ffmpeg_tonemap_enabled = True

    port = 8003
    temp_folder: pathlib.Path = os.path.join(tempfile.gettempdir(), 'seplis_play')
    thumbnails_path: pathlib.Path | None
    session_timeout = 10 # Timeout for HLS sessions
    server_id: str
    api_url: AnyHttpUrl = 'https://api.seplis.net'
    logging = ConfigLoggingModel()
    sentry_dsn: str | None

    class Config:
        env_prefix = 'seplis_play_'
        env_nested_delimiter = '.'
        validate_assignment = True
        case_sensitive = False


default_paths = [
    '~/seplis_play_server.yaml',
    './seplis_play_server.yaml',
    '/etc/seplis/seplis_play_server.yaml',
    '/etc/seplis_play_server.yaml',
]
path = os.environ.get('SEPLIS_PLAY_SERVER_CONFIG', None)
if not path:
    for p in default_paths:
        p = os.path.expanduser(p)
        if os.path.isfile(p):
            path = p
            break

config = None
if path:
    with open(path) as f:
        data = yaml.load(f, Loader=yaml.SafeLoader)
        if data:
            config = ConfigModel(**data)
if not config:
    config = ConfigModel()

if config.temp_folder:
    try:
        os.makedirs(config.temp_folder, exist_ok=True)
    except:
        pass