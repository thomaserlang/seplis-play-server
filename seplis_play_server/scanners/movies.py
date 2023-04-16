import asyncio
import sqlalchemy as sa
from datetime import datetime, timezone
from seplis_play_server import config, utils, logger, models, schemas
from seplis_play_server.client import client
from seplis_play_server.database import database
from guessit import guessit
from .base import Play_scan


class Movie_scan(Play_scan):

    async def scan(self):
        logger.info(f'Scanning: {self.scan_path}')
        files = self.get_files()
        for f in files:
            title = self.parse(f)
            if title:
                await self.save_item(title, f)


    def parse(self, filename):
        d = guessit(filename, {
            'type': 'movie',
            'excludes': ['country', 'language', 'film'],
        })
        if d and d.get('title'):
            t = d['title']
            if d.get('part'):
                t += f' Part {d["part"]}'
            if d.get('year'):
                t += f" ({d['year']})"
            return t        
        logger.info(f'{filename} doesn\'t look like a movie')


    async def save_item(self, item: str, path: str):
        async with database.session() as session:
            movie = await session.scalar(sa.select(models.Movie).where(
                models.Movie.path == path,
            ))
            movie_id = movie.movie_id if movie else None
            modified_time = self.get_file_modified_time(path)
            
            if not movie or (movie.modified_time != modified_time) or not movie.meta_data:
                if not movie_id:
                    movie_id = await self.lookup(item)
                    if not movie_id:
                        logger.info(f'No movie found for {item} ({path})')
                        return
                try:
                    metadata = await self.get_metadata(path)
                    if not metadata:
                        return

                    if movie:
                        sql = sa.update(models.Movie).where(
                            models.Movie.path == path,
                        ).values({
                            models.Movie.movie_id: movie_id,
                            models.Movie.meta_data: metadata,
                            models.Movie.modified_time: modified_time,
                        })
                    else:
                        sql = sa.insert(models.Movie).values({
                            models.Movie.movie_id: movie_id,
                            models.Movie.path: path,
                            models.Movie.meta_data: metadata,
                            models.Movie.modified_time: modified_time,
                        })
                    await session.execute(sql)
                    await session.commit()

                    await self.add_to_index(movie_id=movie_id, created_at=modified_time)

                    logger.info(f'[movie-{movie_id}] Saved {path}')
                except Exception as e:
                    logger.error(str(e))
            else:
                logger.debug(f'[movie-{movie_id}] Nothing changed for {path}')
            if self.make_thumbnails:
                asyncio.create_task(self.thumbnails(f'movie-{movie_id}', path))
            return True


    async def add_to_index(self, movie_id: int, created_at: datetime = None):
        if self.cleanup_mode:
            return

        if not config.server_id:
            logger.warn(f'[movie-{movie_id}] No server_id specified')

        r = await client.patch(f'/2/play-servers/{config.server_id}/movies', data=utils.json_dumps([
            schemas.Play_server_movie_create(
                movie_id=movie_id,
                created_at=created_at or datetime.now(tz=timezone.utc)
            )
        ]), headers={
            'Authorization': f'Secret {config.secret}',
            'Content-Type': 'application/json',
        })
        if r.status_code >= 400:
            logger.error(f'[movie-{movie_id}] Faild to add the movie to the play server index ({config.server_id}): {r.content}')
        else:
            logger.info(f'[movie-{movie_id}] Added to play server index ({config.server_id})')


    async def lookup(self, title: str):
        logger.debug(f'Looking for a movie with title: "{title}"')
        async with database.session() as session:
            movie = await session.scalar(sa.select(models.Movie_id_lookup).where(
                models.Movie_id_lookup.file_title == title,
            ))
            if not movie:
                r = await client.get('/2/search', params={
                    'title': title,
                    'type': 'movie',
                })
                r.raise_for_status()
                movies = r.json()
                if not movies:
                    return
                logger.debug(f'[movie-{movies[0]["id"]}] Found: {movies[0]["title"]}')
                movie = models.Movie_id_lookup(
                    file_title=title,
                    movie_title=movies[0]["title"],
                    movie_id=movies[0]["id"],
                    updated_at=datetime.now(tz=timezone.utc),
                )
                await session.merge(movie)
                await session.commit()
                return movie.movie_id
            else:                
                logger.debug(f'[movie-{movie.movie_id}] Found from cache: {movie.movie_title}')
                return movie.movie_id


    async def delete_path(self, path):
        async with database.session() as session:
            movie_id = await session.scalar(sa.select(models.Movie.movie_id).where(
                models.Movie.path == path,
            ))
            if movie_id:
                await session.execute(sa.delete(models.Movie).where(
                    models.Movie.path == path,
                ))
                await session.commit()

                await self.delete_from_index(movie_id=movie_id, session=session)

                logger.info(f'[movie-{movie_id}] Deleted: {path}')
                return True
                
        return False


    async def delete_from_index(self, movie_id: int, session):
        if self.cleanup_mode:
            return
        if config.server_id:
            m = await session.scalar(sa.select(models.Movie).where(
                models.Movie.movie_id == movie_id,
            ))
            if m:
                return
            r = await client.delete(f'/2/play-servers/{config.server_id}/movies/{movie_id}',
                headers={
                    'Authorization': f'Secret {config.secret}'
                }
            )
            if r.status_code >= 400:
                logger.error(f'[movie-{movie_id}] Failed to add the movie to the play server index: {r.content}')
            else:
                logger.info(f'[movie-{movie_id}] Deleted from play server index')
        else:
            logger.warn(f'[movie-{movie_id}] No server_id specified')
