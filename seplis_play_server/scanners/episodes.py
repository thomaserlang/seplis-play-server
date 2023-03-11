import asyncio
import os.path, re
import sqlalchemy as sa
from datetime import datetime, timezone
from seplis_play_server import constants, models, config, utils, logger, schemas
from seplis_play_server.client import client
from seplis_play_server.database import database
from .base import Play_scan


class Episode_scan(Play_scan):

    def __init__(self, scan_path: str, make_thumbnails: bool = False, cleanup_mode = False):
        super().__init__(
            scan_path=scan_path,
            type_='series',
            make_thumbnails=make_thumbnails,
            cleanup_mode=cleanup_mode,
        )
        self.series_id = Series_id(scanner=self)
        self.episode_number = Episode_number(scanner=self)
        self.not_found_series = []

    async def scan(self):
        logger.info(f'Scanning: {self.scan_path}')
        files = self.get_files()
        for f in files:
            episode = self.parse(f)
            if episode:
                await self.save_item(episode, f)
            else:
                logger.debug(f'"{f}" didn\'t match any pattern')

    def parse(self, filename):
        for pattern in constants.SERIES_FILENAME_PATTERNS:
            try:
                match = re.match(
                    pattern, 
                    os.path.basename(filename), 
                    re.VERBOSE | re.IGNORECASE
                )
                if not match:
                    continue
                return self._parse_episode_info_from_file(match=match)
            except re.error as error:
                logger.exception(f'episode parse re error: {error}')
            except:
                logger.exception(f'episode parse pattern: {pattern}')

    async def episode_series_id_lookup(self, episode):
        '''

        :param episode: `Parsed_episode()`
        :returns: bool
        '''
        if episode.file_title in self.not_found_series:
            return False
        logger.debug(f'Looking for a series with title: "{episode.file_title}"')
        series_id = await self.series_id.lookup(episode.file_title)
        if series_id:
            logger.debug(f'[series-{series_id}] Found: "{episode.file_title}"')
            episode.series_id = series_id
            return True
        else:
            self.not_found_series.append(episode.file_title)
            logger.info(f'No series found for title: "{episode.file_title}"')
        return False

    async def episode_number_lookup(self, episode):
        '''
        Tries to lookup the episode number of the episode.
        Sets the number in the episode object if successful.

        :param episode: `Parsed_episode()`
        :returns: bool
        '''
        if not episode.series_id:
            return
        if isinstance(episode, Parsed_episode_number):
            return True
        value = self.episode_number.get_lookup_value(episode)
        logger.debug(f'[series-{episode.series_id}] Looking for episode {value}')
        number = await self.episode_number.lookup(episode)
        if number:                
            logger.debug(f'[episodes-{episode.series_id}-{number}] Found episode')
            episode.number = number
            return True
        else:
            logger.info(f'[series-{episode.series_id}] No episode found for {value}')
        return False

    async def save_item(self, item, path):
        '''
        :param episode: `Parsed_episode()`
        :returns: bool
        '''
        if not item.series_id:
            if not await self.episode_series_id_lookup(item):
                return False
        if not item.number:
            if not await self.episode_number_lookup(item):
                return False
        async with database.session() as session:
            ep = await session.scalar(sa.select(models.Episode).where(
                models.Episode.series_id == item.series_id,
                models.Episode.number == item.number,
                models.Episode.path == path,
            ))

            modified_time = self.get_file_modified_time(path)
            if not ep or (ep.modified_time != modified_time) or not ep.meta_data:
                metadata = await self.get_metadata(path)
                e = models.Episode(
                    series_id=item.series_id,
                    number=item.number,
                    path=path,
                    meta_data=metadata,
                    modified_time=modified_time,
                )
                await session.merge(e)
                await session.commit()

                await self.add_to_index(
                    series_id=item.series_id, 
                    episode_number=item.number,
                    created_at=modified_time,
                )

                logger.info(f'[episode-{item.series_id}-{item.number}] Saved {path}')
            else:                
                logger.info(f'[episode-{item.series_id}-{item.number}] Nothing changed for {path}')
            if self.make_thumbnails:
                asyncio.create_task(self.thumbnails(f'episode-{item.series_id}-{item.number}', path))
            return True

    async def add_to_index(self, series_id: int, episode_number: int, created_at: datetime = None):
        if self.cleanup_mode:
            return

        if not config.server_id:
            logger.warn(f'[episode-{series_id}-{episode_number}] No server_id specified')
            return

        r = await client.patch(f'/2/play-servers/{config.server_id}/episodes', data=utils.json_dumps([
                schemas.Play_server_episode_create(
                    series_id=series_id,
                    episode_number=episode_number,
                    created_at=created_at or datetime.now(tz=timezone.utc),
                )
            ]), headers={
                'Authorization': f'Secret {config.secret}',
                'Content-Type': 'application/json',
            }
        )
        if r.status_code >= 400:
            logger.error(f'[episode-{series_id}-{episode_number}] Faild to add the episode to the play server index: {r.content}')
        else:
            logger.info(f'[episode-{series_id}-{episode_number}] Added to play server index ({config.server_id})')


    async def delete_item(self, item, path):        
        '''
        :param episode: `Parsed_episode()`
        :returns: bool
        '''
        if not item.series_id:
            if not await self.episode_series_id_lookup(item):
                return False
        if not item.number:
            if not await self.episode_number_lookup(item):
                return False
        async with database.session() as session:
            ep = await session.scalar(sa.select(models.Episode.number).where(
                models.Episode.series_id == item.series_id,
                models.Episode.number == item.number,
                models.Episode.path == path,
            ))
            if ep:
                await session.execute(sa.delete(models.Episode).where(                    
                    models.Episode.series_id == item.series_id,
                    models.Episode.number == item.number,
                    models.Episode.path == path,
                ))
                await session.commit()

                await self.delete_from_index(series_id=item.series_id, episode_number=item.number, session=session)

                logger.info(f'[episode-{item.series_id}-{item.number}] Deleted: {path}')
                return True
        return False

    async def delete_from_index(self, series_id: int, episode_number: int, session):
        if self.cleanup_mode:
            return

        m = await session.scalar(sa.select(models.Episode).where(
            models.Episode.series_id == series_id,
            models.Episode.number == episode_number,
        ))
        if m:
            return
            
        if not config.server_id:
            logger.warn(f'[episode-{series_id}-{episode_number}] No server_id specified')
            return

        r = await client.delete(f'/2/play-servers/{config.server_id}/series/{series_id}/episodes/{episode_number}', 
            headers={
                'Authorization': f'Secret {config.secret}'
            }
        )
        if r.status_code >= 400:
            logger.error(f'[episode-{series_id}-{episode_number}] Faild to inform that we have the episode: {r.content}')
        else:
            logger.info(f'[episode-{series_id}-{episode_number}] Added to play server index')


    def _parse_episode_info_from_file(self, match):
        fields = match.groupdict().keys()
        season = None
        if 'file_title' not in fields:
            return None
        file_title = match.group('file_title').strip().lower()

        season = None
        if 'season' in fields:
            season = int(match.group('season'))

        number = None
        if 'number' in fields:
            number = match.group('number')
        elif 'number1' in fields:
            number = match.group('number1')
        elif 'numberstart' in fields:
            number = match.group('numberstart')
        if number:
            number = int(number)

        air_date = None
        if 'year' in fields and 'month' in fields and 'day' in fields:
            air_date = '{}-{}-{}'.format(
                match.group('year'),
                match.group('month'),
                match.group('day'),
            )

        if season and number:
            return Parsed_episode_season(
                file_title=file_title,
                season=season,
                episode=number,
            )
        elif not season and number:
            return Parsed_episode_number(
                file_title=file_title,
                number=number,
            )
        elif air_date:
            return Parsed_episode_air_date(
                file_title=file_title,
                air_date=air_date,
            )

class Parsed_episode(object):

    def __init__(self):
        self.lookup_type = 0
        self.series_id = None
        self.number = None

class Parsed_episode_season(Parsed_episode):

    def __init__(self, file_title, season, episode, series_id=None, number=None):
        super().__init__()
        self.lookup_type = 1
        self.file_title = file_title
        self.season = season
        self.episode = episode
        self.series_id = series_id
        self.number = number

class Parsed_episode_air_date(Parsed_episode):

    def __init__(self, file_title, air_date, series_id=None, number=None):
        super().__init__()
        self.lookup_type = 2
        self.file_title = file_title
        self.air_date = air_date
        self.series_id = series_id
        self.number = number

class Parsed_episode_number(Parsed_episode):

    def __init__(self, file_title, number, series_id=None):
        super().__init__()
        self.file_title = file_title
        self.number = number
        self.series_id = series_id

class Series_id(object):
    '''Used to lookup a series id by it's title.
    The result will be cached in the local db.
    '''

    def __init__(self, scanner):
        self.scanner = scanner

    async def lookup(self, file_title):
        '''
        Tries to find the series on SEPLIS by it's title.

        :param file_title: str
        :returns: int
        '''
        series_id = await self.db_lookup(file_title)
        if series_id:
            return series_id
        series = await self.web_lookup(file_title)
        series_id = series[0]['id'] if series else None
        series_title = series[0]['title'] if series else None
        async with database.session() as session:
            series = models.Series_id_lookup(
                file_title=file_title,
                series_title=series_title,
                series_id=series_id,
                updated_at=datetime.utcnow(),
            )
            await session.merge(series)
            await session.commit()
        return series_id

    async def db_lookup(self, file_title):        
        '''

        :param file_title: str
        :returns: int
        '''
        async with database.session() as session:
            series = await session.scalar(sa.select(models.Series_id_lookup).where(
                models.Series_id_lookup.file_title == file_title,
            ))
            if not series or not series.series_id:
                return
            return series.series_id

    async def web_lookup(self, file_title):
        r = await client.get('/2/search', params={
            'title': file_title,
            'type': 'series',
        })
        r.raise_for_status()
        return r.json()

class Episode_number(object):
    '''Used to lookup an episode's number from the season and episode or
    an air date.
    Stores the result in the local db.
    '''

    def __init__(self, scanner):
        self.scanner = scanner

    async def lookup(self, episode):
        if not episode.series_id:
            raise Exception('series_id must be defined in the episode object')
        if isinstance(episode, Parsed_episode_number):
            return episode.number
        number = await self.db_lookup(episode)
        if number:
            return number
        number = await self.web_lookup(episode)
        if not number:
            return
        async with database.session() as session:
            await session.execute(sa.insert(models.Episode_number_lookup).values(
                series_id=episode.series_id,
                lookup_type=episode.lookup_type,
                lookup_value=self.get_lookup_value(episode),
                number=number,
            ))
            await session.commit()
        return number

    async def db_lookup(self, episode):
        async with database.session() as session:
            value = self.get_lookup_value(episode)
            e = await session.scalar(sa.select(models.Episode_number_lookup.number).where(
                models.Episode_number_lookup.series_id == episode.series_id,
                models.Episode_number_lookup.lookup_type == episode.lookup_type,
                models.Episode_number_lookup.lookup_value == value,
            ))
            if not e:
                return
            return e

    @staticmethod
    def get_lookup_value(episode):
        value = None
        if isinstance(episode, Parsed_episode_season):
            value = '{}-{}'.format(
                episode.season,
                episode.episode,
            )
        elif isinstance(episode, Parsed_episode_air_date):
            value = '{}'.format(
                episode.air_date,
            )
        else:
            raise Exception('''
                Unknown parsed episode object. 
                If the episode already contains a number there is no need 
                to use this method.
            ''')
        return value

    async def web_lookup(self, episode):
        params = {}
        if isinstance(episode, Parsed_episode_season):
            params = {
                'season': episode.season,
                'episode': episode.episode,
            }
        elif isinstance(episode, Parsed_episode_air_date):
            params = {
                'air_date': episode.air_date,
            }
        else:
            raise Exception('Unknown parsed episode object')
        r = await client.get(f'/2/series/{episode.series_id}/episodes', params=params)
        r.raise_for_status()
        episodes = schemas.Page_cursor_result[schemas.Episode].parse_obj(r.json())
        if not episodes.items:
            return
        return episodes.items[0].number