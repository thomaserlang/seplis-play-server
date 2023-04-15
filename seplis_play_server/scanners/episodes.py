import asyncio
import os.path, re
import sqlalchemy as sa
from guessit import guessit
from datetime import date, datetime, timezone
from seplis_play_server import constants, models, config, utils, logger, schemas
from seplis_play_server.client import client
from seplis_play_server.database import database
from .base import Play_scan


class Episode_scan(Play_scan):

    def __init__(self, scan_path: str, make_thumbnails: bool = False, cleanup_mode = False, parser = 'internal'):
        super().__init__(scan_path, make_thumbnails, cleanup_mode, parser)
        self.series_id = Series_id_lookup(scanner=self)
        self.episode_number = Episode_number_lookup(scanner=self)
        self.not_found_series = []


    async def scan(self):
        logger.info(f'Scanning: {self.scan_path}')
        files = self.get_files()
        for f in files:
            parsed_episode = self.parse(f)
            if parsed_episode:
                await self.save_item(parsed_episode, f)
            else:
                logger.debug(f'"{f}" didn\'t match any pattern')


    def parse(self, filename):
        if self.parser == 'guessit':
            return self.guessit_parse_file_name(filename)
        return self.regex_parse_file_name(filename)


    async def episode_series_id_lookup(self, episode: schemas.Parsed_file_episode):
        if episode.title in self.not_found_series:
            return False
        logger.debug(f'Looking for a series with title: "{episode.title}"')
        series_id = await self.series_id.lookup(episode.title)
        if series_id:
            logger.debug(f'[series-{series_id}] Found: "{episode.title}"')
            episode.series_id = series_id
            return True
        else:
            self.not_found_series.append(episode.title)
            logger.info(f'No series found for title: "{episode.title}"')
        return False


    async def episode_number_lookup(self, episode: schemas.Parsed_file_episode):
        '''
        Tries to lookup the episode number of the episode.
        Sets the number in the episode object if successful.
        '''
        if not episode.series_id:
            return
        if episode.episode_number:
            return True
        value = self.episode_number.get_lookup_value(episode)
        if not value:
            return
        logger.debug(f'[series-{episode.series_id}] Looking for episode {value}')
        number = await self.episode_number.lookup(episode)
        if number:                
            logger.debug(f'[episodes-{episode.series_id}-{number}] Found episode')
            episode.episode_number = number
            return True
        else:
            logger.info(f'[series-{episode.series_id}] No episode found for {value}')
        return False


    async def save_item(self, item: schemas.Parsed_file_episode, path: str):
        async with database.session() as session:
            ep = await session.scalar(sa.select(models.Episode).where(
                models.Episode.path == path,
            ))
            if ep:
                item.series_id = ep.series_id
                item.episode_number = ep.number
            modified_time = self.get_file_modified_time(path)
            if not ep or (ep.modified_time != modified_time) or not ep.meta_data:
                if not ep:
                    if not item.series_id:
                        if not await self.episode_series_id_lookup(item):
                            logger.info(f'No series found for file {path}')
                            return False
                    if not item.episode_number:
                        if not await self.episode_number_lookup(item):
                            logger.info(f'No episode found for file {path}')
                            return False
                try:
                    metadata = await self.get_metadata(path)

                    if ep:
                        sql = sa.update(models.Episode).where(
                            models.Episode.path == path,
                        ).values({
                            models.Episode.meta_data: metadata,
                            models.Episode.modified_time: modified_time,
                        })
                    else:
                        sql = sa.insert(models.Episode).values({
                            models.Episode.series_id: item.series_id,
                            models.Episode.number: item.episode_number,
                            models.Episode.path: path,
                            models.Episode.meta_data: metadata,
                            models.Episode.modified_time: modified_time,
                        })
                    await session.execute(sql)
                    await session.commit()

                    await self.add_to_index(
                        series_id=item.series_id, 
                        episode_number=item.episode_number,
                        created_at=modified_time,
                    )

                    logger.info(f'[episode-{item.series_id}-{item.episode_number}] Saved {path}')
                except Exception as e:
                    logger.error(str(e))
            else:                
                logger.info(f'[episode-{item.series_id}-{item.episode_number}] Nothing changed for {path}')
            if self.make_thumbnails:
                asyncio.create_task(self.thumbnails(f'episode-{item.series_id}-{item.episode_number}', path))
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


    async def delete_path(self, path):
        async with database.session() as session:
            episode = await session.scalar(sa.select(models.Episode).where(
                models.Episode.path == path,
            ))
            if episode:
                await session.execute(sa.delete(models.Episode).where(
                    models.Episode.path == path,
                ))
                await session.commit()

                await self.delete_from_index(series_id=episode.series_id, episode_number=episode.number, session=session)

                logger.info(f'[episode-{episode.series_id}-{episode.number}] Deleted: {path}')
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
            logger.error(f'[episode-{series_id}-{episode_number}] Faild to remove the episode from the play server index: {r.content}')
        else:
            logger.info(f'[episode-{series_id}-{episode_number}] Removed from play server index')


    def regex_parse_file_name(self, filename: str) -> schemas.Parsed_file_episode: 
        result = schemas.Parsed_file_episode()
        for pattern in constants.SERIES_FILENAME_PATTERNS:
            try:
                match = re.match(
                    pattern, 
                    os.path.basename(filename), 
                    re.VERBOSE | re.IGNORECASE
                )
                if not match:
                    continue

                fields = match.groupdict().keys()
                if 'file_title' not in fields:
                    continue
                
                if not result.title:
                    result.title = match.group('file_title').strip().lower()

                if 'season' in fields and not result.season:
                    result.season = int(match.group('season'))
                if 'episode' in fields and not result.season:
                    result.episode = int(match.group('episode'))

                number = None
                if 'episode' in fields:
                    number = match.group('episode')
                elif 'episode_start' in fields:
                    number = match.group('episode_start')
                if number and not result.episode:
                    if not result.season:
                        if not result.episode_number:
                            result.episode_number = int(number)
                    else:
                        result.episode = int(number)

                if 'absolute_number' in fields and not result.episode_number:
                    result.episode_number = int(match.group('absolute_number'))

                if 'year' in fields and 'month' in fields and 'day' in fields and not result.date:
                    result.date = date(int(match.group('year')), int(match.group('month')), int(match.group('day')))
                
            except re.error as error:
                logger.exception(f'episode parse re error: {error}')
            except:
                logger.exception(f'episode parse pattern: {pattern}')

        return result if result.title and (result.episode_number or (result.season and result.episode)) else None


    def guessit_parse_file_name(self, filename: str) -> schemas.Parsed_file_episode:
        d = guessit(filename, {
            'type': 'episode',
            'episode_prefer_number': True,
            'excludes': ['country', 'language'],
        })
        if d and d.get('title'):
            result = schemas.Parsed_file_episode()
            result.title = d['title'].strip().lower()
            if d.get('year'):
                result.title += f' ({d["year"]})'
            if d.get('season'):
                result.season = d['season']
            if d.get('episode'):
                result.episode = d['episode']
            if d.get('episode_number'):
                result.episode_number = d['episode']
            if d.get('date'):
                result.date = d['date']
            return result
        else:
            logger.info(f'{filename} doesn\'t look like an episode')


class Series_id_lookup(object):
    '''Used to lookup a series id by it's title.
    The result will be cached in the local db.
    '''

    def __init__(self, scanner):
        self.scanner = scanner

    async def lookup(self, file_title: str):
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

    async def db_lookup(self, file_title: str):
        async with database.session() as session:
            series = await session.scalar(sa.select(models.Series_id_lookup).where(
                models.Series_id_lookup.file_title == file_title,
            ))
            if not series or not series.series_id:
                return
            return series.series_id

    async def web_lookup(self, file_title: str):
        r = await client.get('/2/search', params={
            'title': file_title,
            'type': 'series',
        })
        r.raise_for_status()
        return r.json()

class Episode_number_lookup(object):
    '''Used to lookup an episode's number from the season and episode or
    an air date.
    Stores the result in the local db.
    '''

    def __init__(self, scanner):
        self.scanner = scanner

    async def lookup(self, episode: schemas.Parsed_file_episode):
        if not episode.series_id:
            raise Exception('series_id must be defined in the episode object')
        if episode.episode_number:
            return episode.episode_number
        number = await self.db_lookup(episode)
        if number:
            return number
        number = await self.web_lookup(episode)
        if not number:
            return
        async with database.session() as session:
            await session.execute(sa.insert(models.Episode_number_lookup).values(
                series_id=episode.series_id,
                lookup_type=1,
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
                models.Episode_number_lookup.lookup_type == 1,
                models.Episode_number_lookup.lookup_value == value,
            ))
            if not e:
                return
            return e

    @staticmethod
    def get_lookup_value(episode: schemas.Parsed_file_episode):
        value = None
        if episode.season and episode.episode:
            value = f'{episode.season}-{episode.episode}'
        elif episode.date:
            value = episode.date.strftime('%Y-%m-%d')
        return value

    async def web_lookup(self, episode):
        params = {}
        if episode.season and episode.episode:
            params = {
                'season': episode.season,
                'episode': episode.episode,
            }
        elif episode.date:
            params = {
                'air_date': episode.date.strftime('%Y-%m-%d'),
            }
        else:
            raise Exception('Unknown parsed episode object')
        r = await client.get(f'/2/series/{episode.series_id}/episodes', params=params)
        r.raise_for_status()
        episodes = schemas.Page_cursor_result[schemas.Episode].parse_obj(r.json())
        if not episodes.items:
            return
        return episodes.items[0].number