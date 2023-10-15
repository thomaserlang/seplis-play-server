
from iso639 import Lang
import sqlalchemy as sa
from seplis_play_server.database import database
from seplis_play_server import config, models, logger
from .base import Play_scan
from seplis_play_server import logger


class Subtitle_scan(Play_scan):

    EXTS = config.subtitle_types

    async def save_item(self, item, path):
        async with database.session() as session:
            s = await session.scalar(sa.select(models.External_subtitle).where(
                models.External_subtitle.path == path,
            ))
            if not s:
                await session.execute(sa.insert(models.External_subtitle).values({
                    'path': path,
                    **item,
                }))
                await session.commit()
                logger.info(f'Added subtitle: {path}')

    def parse(self, filename):
        data = filename.rsplit('.', 3)
        if len(data) < 3:
            logger.info(f'{filename} doesn\'t look like a subtitle')
            return
        r = {
            'language': None,
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
                except:
                    continue
        if not r['language']:
            logger.info(f'{filename} doesn\'t have a recognized language')
            return
        return r

    async def delete_path(self, path):
        async with database.session() as session:
            s = await session.scalar(sa.select(models.External_subtitle).where(
                models.External_subtitle.path == path,
            ))
            if s:
                await session.execute(sa.delete(models.External_subtitle).where(
                    models.External_subtitle.path == path,
                ))
                await session.commit()
                logger.info(f'Deleted subtitle: {path}')
            else:
                logger.info(f'Subtitle not found: {path}')
    
    async def get_paths_matching_base_path(self, base_path):
        async with database.session() as session:
            results = await session.scalars(sa.select(models.External_subtitle.path).where(
                models.External_subtitle.path.like(f'{base_path}%'),
            ))
            return [r for r in results]

    async def get_metadata(self, path):
        pass