from datetime import date, datetime
from typing import Any, cast
from unittest import mock

import httpx
import pytest
import respx
import sqlalchemy as sa

from seplis_play.database import Database
from seplis_play.scan import EpisodeScan
from seplis_play.scanners.episode.episode_models import MEpisode
from seplis_play.scanners.episode.episode_schemas import Episode, ParsedFileEpisode
from seplis_play.schemas.page_cursor_schema import PageCursorResult
from seplis_play.schemas.source_metadata_schemas import SourceMetadata
from seplis_play.testbase import run_file


@pytest.mark.asyncio
async def test_get_files() -> None:
    from seplis_play.scanners import EpisodeScan

    scanner = EpisodeScan(scan_path='/', cleanup_mode=True, make_thumbnails=False)
    with mock.patch('os.walk') as mockwalk:
        mockwalk.return_value = [
            ('/series', ('NCIS', 'Person of Interest'), ()),
            ('/series/NCIS', ('Season 01', 'Season 02'), ()),
            (
                '/series/NCIS/Season 01',
                (),
                (
                    'NCIS.S01E01.Yankee White.avi',
                    'NCIS.S01E02.Hung Out to Dry.avi',
                ),
            ),
            (
                '/series/NCIS/Season 02',
                (),
                (
                    'NCIS.S02E01.See No Evil.avi',
                    'NCIS.S02E02.The Good Wives Club.avi',
                ),
            ),
            ('/series/Person of Interest', ('Season 01'), ()),
            (
                '/series/Person of Interest/Season 01',
                (),
                (
                    'Person of Interest.S01E01.Pilot.mp4',
                    '._Person of Interest.S01E01.Pilot.mp4',
                ),
            ),
        ]

        files = scanner.get_files()
        assert files == [
            '/series/NCIS/Season 01/NCIS.S01E01.Yankee White.avi',
            '/series/NCIS/Season 01/NCIS.S01E02.Hung Out to Dry.avi',
            '/series/NCIS/Season 02/NCIS.S02E01.See No Evil.avi',
            '/series/NCIS/Season 02/NCIS.S02E02.The Good Wives Club.avi',
            '/series/Person of Interest/Season 01/Person of Interest.S01E01.Pilot.mp4',
        ]


@pytest.mark.asyncio
@respx.mock
async def test_series_id_lookup(play_db_test: Database) -> None:
    from seplis_play.scanners import EpisodeScan

    scanner = EpisodeScan(scan_path='/', cleanup_mode=True, make_thumbnails=False)

    respx.get('/2/search').mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    'id': 1,
                    'title': 'Test series',
                }
            ],
        )
    )

    assert not await scanner.series_id.db_lookup('test series')
    assert 1 == await scanner.series_id.lookup('test series')
    assert 1 == await scanner.series_id.db_lookup('test series')


@pytest.mark.asyncio
async def test_save_item(play_db_test: Database) -> None:
    scanner = EpisodeScan(scan_path='/', cleanup_mode=True, make_thumbnails=False)
    mock_get_file_modified_time = mock.MagicMock(
        return_value=datetime(2014, 11, 14, 21, 25, 58)
    )
    cast(Any, scanner).get_file_modified_time = mock_get_file_modified_time
    mock_get_metadata = mock.AsyncMock(
        return_value=cast(
            SourceMetadata,
            {
                'some': 'data',
            },
        )
    )
    cast(Any, scanner).get_metadata = mock_get_metadata
    episodes = []
    episodes.append(
        (
            ParsedFileEpisode(
                series_id=1,
                title='ncis',
                season=1,
                episode=2,
                episode_number=2,
            ),
            '/ncis/ncis.s01e02.mp4',
        )
    )
    episodes.append(
        (
            ParsedFileEpisode(
                series_id=1,
                title='ncis',
                date=date(2014, 11, 14),
                episode_number=3,
            ),
            '/ncis/ncis.2014-11-14.mp4',
        )
    )
    episodes.append(
        (
            ParsedFileEpisode(
                series_id=1,
                title='ncis',
                episode_number=4,
            ),
            '/ncis/ncis.4.mp4',
        )
    )
    with mock.patch('os.path.exists') as mock_get_files:
        mock_get_files.return_value = True
        for episode in episodes:
            await scanner.save_item(episode[0], episode[1])

    mock_get_metadata.assert_has_calls(
        [
            mock.call('/ncis/ncis.s01e02.mp4'),
            mock.call('/ncis/ncis.2014-11-14.mp4'),
            mock.call('/ncis/ncis.4.mp4'),
        ]
    )

    mock_get_metadata.reset_mock()
    for episode in episodes:
        await scanner.save_item(episode[0], episode[1])
    mock_get_metadata.assert_has_calls([])

    mock_get_metadata.reset_mock()
    mock_get_file_modified_time.return_value = datetime(2014, 11, 15, 21, 25, 58)
    with mock.patch('os.path.exists') as mock_get_files:
        await scanner.save_item(episodes[1][0], episodes[1][1])
    mock_get_metadata.assert_has_calls(
        [mock.call('/ncis/ncis.2014-11-14.mp4')],
    )

    async with play_db_test.session() as session:
        r = await session.scalars(sa.select(MEpisode))
        r = r.all()
        assert len(r) == 3

    await scanner.delete_path(episodes[0][1])

    async with play_db_test.session() as session:
        r = await session.scalars(sa.select(MEpisode))
        r = r.all()
        assert len(r) == 2


@pytest.mark.asyncio
@respx.mock
async def test_episode_number_lookup(play_db_test: Database) -> None:
    from seplis_play.scanners import EpisodeScan

    scanner = EpisodeScan(scan_path='/', cleanup_mode=True, make_thumbnails=False)

    respx.get('/2/series/1/episodes', params={'season': '1', 'episode': '2'}).mock(
        return_value=httpx.Response(
            200,
            json=PageCursorResult[Episode](items=[Episode(number=2)]).model_dump(),
        )
    )
    episode = ParsedFileEpisode(
        series_id=1,
        title='NCIS',
        season=1,
        episode=2,
    )
    assert not await scanner.episode_number.db_lookup(episode)
    assert 2 == await scanner.episode_number.lookup(episode)
    assert 2 == await scanner.episode_number.db_lookup(episode)

    respx.get('/2/series/1/episodes', params={'air_date': '2014-11-14'}).mock(
        return_value=httpx.Response(
            200,
            json=PageCursorResult[Episode](items=[Episode(number=3)]).model_dump(),
        )
    )
    episode = ParsedFileEpisode(
        series_id=1,
        title='NCIS',
        date=date(2014, 11, 14),
    )
    assert not await scanner.episode_number.db_lookup(episode)
    assert 3 == await scanner.episode_number.lookup(episode)
    assert 3 == await scanner.episode_number.db_lookup(episode)

    episode = ParsedFileEpisode(
        series_id=1,
        title='NCIS',
        episode_number=4,
    )
    assert await scanner.episode_number_lookup(episode)
    assert 4 == await scanner.episode_number.lookup(episode)


@pytest.mark.asyncio
async def test_parse_episodes(play_db_test: Database) -> None:
    from seplis_play.scanners import EpisodeScan

    scanner = EpisodeScan(scan_path='/', cleanup_mode=True, make_thumbnails=False)

    path = (
        '/Alpha House/Alpha.House.S02E01.The.Love.Doctor.720p.'
        'AI.WEBRip.DD5.1.x264-NTb.mkv'
    )
    info = scanner.parse(path)
    assert info
    assert info.title == 'alpha.house'
    assert info.season == 2
    assert info.episode == 1

    path = '/Naruto/[HorribleSubs] Naruto Shippuuden - 379 [1080p].mkv'
    info = scanner.parse(path)
    assert info
    assert info.title == 'naruto shippuuden'
    assert info.episode_number == 379

    path = '/Naruto Shippuuden/Naruto Shippuuden.426.720p.mkv'
    info = scanner.parse(path)
    assert info
    assert info.title, 'naruto shippuuden'
    assert info.episode_number == 426

    path = (
        '/The Daily series/The.Daily.series.2014.06.03.Ricky.Gervais.HDTV.x264-D0NK.mp4'
    )
    info = scanner.parse(path)
    assert info
    assert info.title, 'the.daily.series'
    assert info.date
    assert info.date.strftime('%Y-%m-%d') == '2014-06-03'

    path = 'Star Wars Resistance.S01E01-E02.720p webdl h264 aac.mkv'
    info = scanner.parse(path)
    assert info
    assert info.title == 'star wars resistance'
    assert info.season == 1
    assert info.episode == 1

    path = 'Boruto Naruto Next Generations (2017) - 6.1080p h265.mkv'
    info = scanner.parse(path)
    assert info
    assert info.title == 'boruto naruto next generations (2017)'
    assert info.episode_number == 6

    path = 'Boruto Naruto Next Generations (2017).mkv'
    info = scanner.parse(path)
    assert not info

    path = 'Vinland Saga (2019) - S01E01 - 005 - [HDTV-1080p][8bit][h264][AAC 2.0].mkv'
    info = scanner.parse(path)
    assert info
    assert info.season == 1
    assert info.episode == 1
    assert info.episode_number == 5
    assert info.title == 'vinland saga (2019)'

    path = 'The Big Bang Theory (2007) - S04E01 [Bluray-1080p][AAC 5.1][x265].mkv'
    info = scanner.parse(path)
    assert info
    assert info.season == 4
    assert info.episode == 1
    assert not info.episode_number
    assert info.title == 'the big bang theory (2007)'

    path = 'Vinland Saga (2019) - S01E01 - 005 - [HDTV-1080p][8bit][h264][AAC 2.0].mkv'
    scanner.parser = 'guessit'
    info = scanner.parse(path)
    assert info
    assert info.season == 1
    assert info.episode == 1
    assert info.title == 'vinland saga (2019)'

    path = 'the last of us - S01E02.mkv'
    scanner.parser = 'guessit'
    info = scanner.parse(path)
    assert info
    assert info.season == 1
    assert info.episode == 2
    assert info.title == 'the last of us'


if __name__ == '__main__':
    run_file(__file__)
