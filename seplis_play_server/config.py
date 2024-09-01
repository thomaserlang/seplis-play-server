import os
import pathlib
import tempfile
from typing import Literal

import yaml
from pydantic import AnyHttpUrl, BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigLoggingModel(BaseModel):
    level: Literal['notset', 'debug', 'info', 'warn', 'error', 'critical'] = 'info'
    path: pathlib.Path | None = None
    max_size: int = 100 * 1000 * 1000 # ~ 95 mb
    num_backups: int = 10


class ConfigPlayScanModel(BaseModel):
    type: Literal['series', 'movies']
    path: pathlib.Path
    make_thumbnails: bool = False
    parser: Literal['internal', 'guessit'] = 'internal'

    
class ConfigModel(BaseSettings):
    debug: bool = False
    test: bool = False
    database: str
    secret: str | None = None
    scan: list[ConfigPlayScanModel] | None = None
    media_types: list[str] = ['mp4', 'mkv', 'avi', 'mpg', 'm4v', 'm2ts']
    subtitle_types: list[str] = ['srt', 'vtt', 'ass']
    subtitle_external_default_language: str = 'en'
    
    ffmpeg_folder: pathlib.Path = '/bin'
    ffmpeg_loglevel: str | int = '40'
    ffmpeg_logfile: pathlib.Path | None = None
    ffmpeg_preset: Literal['veryslow', 'slower', 'slow', 'medium', 'fast', 'faster', 'veryfast', 'superfast', 'ultrafast'] = 'veryfast' 
    ffmpeg_hwaccel_enabled: bool = False
    ffmpeg_hwaccel_device: str = '/dev/dri/renderD128'
    ffmpeg_hwaccel: str = 'qsv'
    ffmpeg_hwaccel_low_powermode: bool = True
    ffmpeg_tonemap_enabled: bool = True
    ffmpeg_segment_threshold_for_new_transcoder: int = 7
    extract_keyframes: bool = True

    port: int = 8003
    transcode_folder: pathlib.Path = os.path.join(tempfile.gettempdir(), 'seplis_play')
    thumbnails_path: pathlib.Path | None = None
    session_timeout: int = 10 # Timeout for HLS sessions
    server_id: str
    api_url: AnyHttpUrl = 'https://api.seplis.net'
    logging: ConfigLoggingModel = ConfigLoggingModel()
    sentry_dsn: str | None = None

    model_config = SettingsConfigDict(
        env_prefix='seplis_play_',
        env_nested_delimiter='.',
        validate_assignment=True,
        case_sensitive=False,
    )


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

if config.transcode_folder:
    try:
        os.makedirs(config.transcode_folder, exist_ok=True)
    except:
        pass