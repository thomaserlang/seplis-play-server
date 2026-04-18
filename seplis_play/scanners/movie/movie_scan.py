import asyncio
import os.path
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from guessit import guessit
from sqlalchemy.ext.asyncio import AsyncSession

from seplis_play import config, logger
from seplis_play.client import client
from seplis_play.database import database
from seplis_play.scanners.movie.movie_models import MMovie, MMovieIdLookup
from seplis_play.scanners.movie.movie_schemas import PlayServerMovieCreate
from seplis_play.schemas.source_metadata_schemas import SourceMetadata

from ..scan_base import PlayScan


class MovieScan(PlayScan):
    SCANNER_NAME = 'Movies'

    def parse(self, filename: str) -> str | None:
        d = guessit(
            filename,
            {
                'type': 'movie',
                'excludes': ['country', 'language', 'film', 'part'],
                'no_user_config': 'true',
            },
        )
        if d and d.get('title'):
            t: str = d['title']
            if d.get('part'):
                t += f' Part {d["part"]}'
            if d.get('year'):
                t += f' ({d["year"]})'
            return t
        logger.info(f"{filename} doesn't look like a movie")
        return None

    async def save_item(self, item: str, path: str) -> bool:
        if not os.path.exists(path):
            logger.debug(f"Path doesn't exist any longer: {path}")
            return False
        async with database.session() as session:
            movie = await session.scalar(
                sa.select(MMovie).where(
                    MMovie.path == path,
                )
            )
            movie_id: int | None = movie.movie_id if movie else None
            modified_time: datetime | None = self.get_file_modified_time(path)

            if not movie or (movie.modified_time != modified_time) or not movie.meta_data:  # type: ignore[operator]
                if not movie_id:
                    movie_id = await self.lookup(item)
                    if not movie_id:
                        logger.info(f'No movie found for {item} ({path})')
                        return False
                try:
                    metadata: SourceMetadata = await self.get_metadata(path)
                    if not metadata:
                        return False

                    if movie:
                        sql = (
                            sa.update(MMovie)
                            .where(
                                MMovie.path == path,
                            )
                            .values(
                                {
                                    MMovie.movie_id: movie_id,
                                    MMovie.meta_data: metadata,
                                    MMovie.modified_time: modified_time,
                                }
                            )
                        )
                    else:
                        sql = sa.insert(MMovie).values(
                            {
                                MMovie.movie_id: movie_id,
                                MMovie.path: path,
                                MMovie.meta_data: metadata,
                                MMovie.modified_time: modified_time,
                            }
                        )
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

    async def add_to_index(
        self, movie_id: int, created_at: datetime | None = None
    ) -> None:
        if self.cleanup_mode:
            return

        if not config.server_id:
            logger.warning(f'[movie-{movie_id}] No server_id specified')

        r = await client.patch(
            f'/2/play-servers/{config.server_id}/movies',
            json=[
                PlayServerMovieCreate(
                    movie_id=movie_id,
                    created_at=created_at or datetime.now(tz=UTC),
                ).model_dump(mode='json')
            ],
            headers={
                'Authorization': f'Secret {config.secret}',
                'Content-Type': 'application/json',
            },
        )
        if r.status_code >= 400:
            logger.error(
                f'[movie-{movie_id}] Faild to add the movie to '
                f'the play server index ({config.server_id}): {r.content}'
            )
        else:
            logger.info(
                f'[movie-{movie_id}] Added to play server index ({config.server_id})'
            )

    async def lookup(self, title: str) -> int | None:
        logger.debug(f'Looking for a movie with title: "{title}"')
        async with database.session() as session:
            movie = await session.scalar(
                sa.select(MMovieIdLookup).where(
                    MMovieIdLookup.file_title == title,
                )
            )
            if not movie:
                r = await client.get(
                    '/2/search',
                    params={
                        'title': title,
                        'type': 'movie',
                    },
                )
                r.raise_for_status()
                movies: list[dict[str, Any]] = r.json()
                if not movies:
                    return None
                logger.debug(f'[movie-{movies[0]["id"]}] Found: {movies[0]["title"]}')
                movie = MMovieIdLookup(
                    file_title=title,
                    movie_title=movies[0]['title'],
                    movie_id=movies[0]['id'],
                    updated_at=datetime.now(tz=UTC),
                )
                await session.merge(movie)
                await session.commit()
                return movie.movie_id
            logger.debug(
                f'[movie-{movie.movie_id}] Found from cache: {movie.movie_title}'
            )
            return movie.movie_id

    async def delete_path(self, path: str) -> bool:
        async with database.session() as session:
            movie_id: int | None = await session.scalar(
                sa.select(MMovie.movie_id).where(
                    MMovie.path == path,
                )
            )
            if movie_id:
                await session.execute(
                    sa.delete(MMovie).where(
                        MMovie.path == path,
                    )
                )
                await session.commit()

                await self.delete_from_index(movie_id=movie_id, session=session)

                logger.info(f'[movie-{movie_id}] Deleted: {path}')
                return True

        return False

    async def delete_from_index(self, movie_id: int, session: AsyncSession) -> None:
        if self.cleanup_mode:
            return
        if config.server_id:
            m: MMovie | None = await session.scalar(
                sa.select(MMovie).where(
                    MMovie.movie_id == movie_id,
                )
            )
            if m:
                return
            r = await client.delete(
                f'/2/play-servers/{config.server_id}/movies/{movie_id}',
                headers={'Authorization': f'Secret {config.secret}'},
            )
            if r.status_code >= 400:
                logger.error(
                    f'[movie-{movie_id}] Failed to add the movie '
                    f'to the play server index: {r.content}'
                )
            else:
                logger.info(f'[movie-{movie_id}] Deleted from play server index')
        else:
            logger.warning(f'[movie-{movie_id}] No server_id specified')

    async def get_paths_matching_base_path(self, base_path: str) -> list[str]:
        async with database.session() as session:
            results = await session.scalars(
                sa.select(MMovie.path).where(MMovie.path.like(f'{base_path}%'))
            )
            return list(results)
