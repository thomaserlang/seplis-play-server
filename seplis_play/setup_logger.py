
import sys
from pathlib import Path

import sentry_sdk
from loguru import logger
from loguru._logger import Logger
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.loguru import LoggingLevels, LoguruIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from seplis_play.config import config


app_logger: Logger = logger


def _log_format() -> str:
    if config.debug:
        return (
            '<green>{time:HH:mm:ss.SSS}</green> | '
            '<level>{level}</level> | '
            '{message} | {extra} | '
            '<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan>'
        )
    return (
        '<green>{time}</green> | '
        '<level>{level}</level> | '
        '{message} | {extra} | '
        '<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan>'
    )


def configure_logger() -> Logger:
    logging_config = config.logging
    app_logger.remove()
    app_logger.add(
        sys.stdout,
        colorize=sys.stdout.isatty(),
        format=_log_format(),
        level=logging_config.level.upper(),
        enqueue=True,
        backtrace=config.debug,
        diagnose=config.debug,
    )
    if logging_config.path is not None:
        log_path = Path(logging_config.path)
        if log_path.is_dir():
            log_path = log_path / 'seplis_play.log'
        app_logger.add(
            log_path,
            format=_log_format(),
            level=logging_config.level.upper(),
            rotation=logging_config.max_size,
            retention=logging_config.num_backups,
            enqueue=True,
            backtrace=config.debug,
            diagnose=config.debug,
        )
    app_logger.bind(config_path=str(config.model_config.get('yaml_file') or 'env')).info(
        'Logger configured'
    )
    return app_logger


if 'pytest' not in sys.modules:
    sentry_sdk.init(
        dsn=config.sentry_dsn,
        send_default_pii=True,
        integrations=[
            LoguruIntegration(
                level=LoggingLevels.INFO.value,
                event_level=LoggingLevels.ERROR.value,
                event_format='{message}',
            ),
            StarletteIntegration(),
            FastApiIntegration(),
        ],
    )

configure_logger()
