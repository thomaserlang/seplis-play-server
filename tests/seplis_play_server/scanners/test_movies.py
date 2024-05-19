from datetime import datetime
from unittest import mock

import httpx
import pytest
import respx
import sqlalchemy as sa

from seplis_play_server import models
from seplis_play_server.database import Database
from seplis_play_server.testbase import run_file


@pytest.mark.asyncio
@respx.mock
async def test_movies(play_db_test: Database):
    from seplis_play_server.scanners import Movie_scan

    scanner = Movie_scan(scan_path='/', cleanup_mode=True, make_thumbnails=False)

    scanner.get_files = mock.MagicMock(
        return_value=[
            'Uncharted.mkv',
        ]
    )
    scanner.get_metadata = mock.AsyncMock(
        return_value={
            'some': 'data',
        }
    )
    scanner.get_file_modified_time = mock.MagicMock(
        return_value=datetime(2014, 11, 14, 21, 25, 58)
    )

    search = respx.get('/2/search').mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    'title': 'Uncharted',
                    'id': 1,
                }
            ],
        )
    )

    with mock.patch('os.path.exists') as mock_get_files:
        mock_get_files.return_value = True
        await scanner.scan()
    assert search.called

    async with play_db_test.session() as session:
        r = await session.scalar(sa.select(models.Movie_id_lookup))
        assert r.file_title == 'Uncharted'

        r = await session.scalar(sa.select(models.Movie))
        assert r.path == 'Uncharted.mkv'
        assert r.meta_data == {'some': 'data'}

    await scanner.delete_path('Uncharted.mkv')
    async with play_db_test.session() as session:
        r = await session.scalar(sa.select(models.Movie))
    assert not r


@pytest.mark.asyncio
async def test_movie_parse():
    from seplis_play_server.scanners import Movie_scan

    scanner = Movie_scan('/')
    assert (
        scanner.parse('Uncharted (2160p BluRay x265 10bit HDR Tigole).mkv')
        == 'Uncharted'
    )
    assert (
        scanner.parse(
            'Parasite.2019.REPACK.2160p.4K.BluRay.x265.10bit.AAC7.1-[YTS.MX].mkv'
        )
        == 'Parasite (2019)'
    )
    assert scanner.parse('F9 (2021) [Bluray-1080p][AAC 5.1][x264].mkv') == 'F9 (2021)'
    assert (
        scanner.parse(
            'Justice League Crisis on Infinite Earths Part Two (2024) [Bluray-1080p Proper][EAC3 5.1][x265]-GalaxyRG265.mkv'
        )
        == 'Justice League Crisis on Infinite Earths Part Two (2024)'
    )


if __name__ == '__main__':
    run_file(__file__)
