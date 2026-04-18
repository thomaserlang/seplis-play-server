import os.path
from typing import NotRequired, TypedDict

import sqlalchemy as sa
from iso639 import Lang

from seplis_play import config, logger
from seplis_play.database import database
from seplis_play.scanners.subtitles.subtitle_models import MExternalSubtitle

from ..scan_base import PlayScan


class SubtitleInfo(TypedDict):
    language: str
    default: bool
    forced: bool
    type: str
    sdh: NotRequired[bool]


class SubtitleScan(PlayScan):
    SCANNER_NAME = 'Subtitles'
    SUPPORTED_EXTS = config.subtitle_types

    async def save_item(self, item: SubtitleInfo, path: str) -> bool:
        if not os.path.exists(path):
            logger.error(f"Path doesn't exist any longer: {path}")
            return False
        async with database.session() as session:
            s = await session.scalar(
                sa.select(MExternalSubtitle).where(
                    MExternalSubtitle.path == path,
                )
            )
            if not s:
                await session.execute(
                    sa.insert(MExternalSubtitle).values(
                        {
                            'path': path,
                            **item,
                        }
                    )
                )
                await session.commit()
                logger.info(f'Added subtitle: {path}')
            return True

    def parse(self, filename: str) -> SubtitleInfo | None:
        data = filename.rsplit('.', 3)
        if len(data) < 3:
            logger.info(f"{filename} doesn't look like a subtitle")
            return None
        r: SubtitleInfo = {
            'language': '',
            'default': False,
            'forced': False,
            'type': data.pop(len(data) - 1),
        }
        for d in data[::-1]:
            d = d.lower()
            if d == 'default':
                r['default'] = True
            elif d == 'forced':
                r['forced'] = True
            elif d == 'sdh':
                r['sdh'] = True
            else:
                try:
                    _ = Lang(d)
                    r['language'] = d
                    break
                except Exception:
                    continue
        if not r['language']:
            r['language'] = config.subtitle_external_default_language
        return r

    async def delete_path(self, path: str) -> bool:
        async with database.session() as session:
            s = await session.scalar(
                sa.select(MExternalSubtitle).where(
                    MExternalSubtitle.path == path,
                )
            )
            if s:
                await session.execute(
                    sa.delete(MExternalSubtitle).where(
                        MExternalSubtitle.path == path,
                    )
                )
                await session.commit()
                logger.info(f'Deleted subtitle: {path}')
            else:
                logger.info(f'Subtitle not found: {path}')
            return True

    async def get_paths_matching_base_path(self, base_path: str) -> list[str]:
        async with database.session() as session:
            results = await session.scalars(
                sa.select(MExternalSubtitle.path).where(
                    MExternalSubtitle.path.like(f'{base_path}%'),
                )
            )
            return [r for r in results]

    async def get_metadata(self, path: str) -> dict[str, str]:
        raise NotImplementedError()
