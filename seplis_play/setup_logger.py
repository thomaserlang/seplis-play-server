import sys

import sentry_sdk
from loguru import logger
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.loguru import LoggingLevels, LoguruIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from seplis_play import config

logger.remove()

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

format = (
    '<green>{time}</green> | '
    '<level>{level}</level> | '
    '{message} | {extra} | '
    '<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan>'
)
if config.debug:
    format = (
        '<green>{time:HH:mm:ss.SSS}</green> | '
        '<level>{level}</level> | '
        '{message} | {extra} | '
        '<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan>'
    )

logger.add(
    sys.stderr,
    colorize=True,
    format=format,
    level=config.logging.level.upper(),
)
