import os
import tempfile
from pathlib import Path
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)


class ConfigLoggingModel(BaseModel):
    level: Literal['notset', 'debug', 'info', 'warning', 'error', 'critical'] = 'info'
    path: Path | None = None
    max_size: int = 100 * 1000 * 1000  # ~ 95 mb
    num_backups: int = 10


class ConfigPlayScanModel(BaseModel):
    type: Literal['series', 'movies']
    path: Path
    make_thumbnails: bool = False
    parser: Literal['internal', 'guessit'] = 'internal'


def get_config_path() -> Path | None:
    path: Path | None = None
    if os.environ.get('SEPLIS_PLAY_CONFIG', None):
        path = Path(os.environ['SEPLIS_PLAY_CONFIG'])

    if not path:
        default_paths = [
            Path(__file__).parent / '../seplis_play.yaml',
            Path('~/seplis_play.yaml'),
            Path('./seplis_play.yaml'),
            Path('/etc/seplis/seplis_play.yaml'),
            Path('/etc/seplis_play.yaml'),
        ]

        for p in default_paths:
            if p.exists():
                path = p
                break
    if not path:
        return None

    path = path.expanduser()
    if not path.exists():
        raise Exception(f'Config file does not exist: {path}')
    return path


class ConfigModel(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix='seplis_play__',
        env_nested_delimiter='__',
        validate_assignment=True,
        case_sensitive=False,
        yaml_file=get_config_path(),
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
            YamlConfigSettingsSource(settings_cls),
        )

    debug: bool = False
    database: str = 'sqlite:///seplis_play.db'
    secret: str | None = None
    scan: list[ConfigPlayScanModel] = []
    media_types: list[str] = ['mp4', 'mkv', 'avi', 'mpg', 'm4v', 'm2ts']
    subtitle_types: list[str] = ['srt', 'vtt', 'ass']
    subtitle_external_default_language: str = 'en'

    ffmpeg_folder: Path = Path('/bin')
    ffmpeg_preset: Literal[
        'veryslow',
        'slower',
        'slow',
        'medium',
        'fast',
        'faster',
        'veryfast',
        'superfast',
        'ultrafast',
    ] = 'veryfast'
    ffmpeg_hwaccel_enabled: bool = False
    ffmpeg_hwaccel_device: str = '/dev/dri/renderD128'
    ffmpeg_hwaccel: str = 'qsv'
    ffmpeg_hwaccel_low_powermode: bool = False
    ffmpeg_tonemap_enabled: bool = True
    ffmpeg_segment_threshold_for_new_transcoder: int = 7
    ffmpeg_pause_threshold_seconds: int = 300
    ffmpeg_resume_threshold_seconds: int = 150

    extract_keyframes: bool = True

    port: int = 8003
    transcode_folder: Path = Path(tempfile.gettempdir()) / 'seplis_play'
    thumbnails_path: Path | None = None
    session_timeout: int = 10  # Timeout for HLS sessions
    server_id: str = ''
    api_url: AnyHttpUrl = AnyHttpUrl('https://api.seplis.net')
    logging: ConfigLoggingModel = ConfigLoggingModel()
    sentry_dsn: str | None = None


config = ConfigModel()
