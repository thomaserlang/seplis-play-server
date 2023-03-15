import pytest
import httpx
import respx
import sqlalchemy as sa
from unittest import mock
from datetime import datetime
from seplis_play_server.testbase import run_file, play_db_test
from seplis_play_server.database import Database
from seplis_play_server import models, schemas


@pytest.mark.asyncio
async def test_get_files():
    from seplis_play_server.scanners import Episode_scan
    scanner = Episode_scan(scan_path='/', cleanup_mode=True, make_thumbnails=False)
    with mock.patch('os.walk') as mockwalk:
        mockwalk.return_value = [                
            ('/series', ('NCIS', 'Person of Interest'), ()),
            ('/series/NCIS', ('Season 01', 'Season 02'), ()),
            ('/series/NCIS/Season 01', (), (
                'NCIS.S01E01.Yankee White.avi',
                'NCIS.S01E02.Hung Out to Dry.avi',
            )),
            ('/series/NCIS/Season 02', (), (
                'NCIS.S02E01.See No Evil.avi',
                'NCIS.S02E02.The Good Wives Club.avi',  
            )),
            ('/series/Person of Interest', ('Season 01'), ()),
            ('/series/Person of Interest/Season 01', (), (
                'Person of Interest.S01E01.Pilot.mp4',
                '._Person of Interest.S01E01.Pilot.mp4',
            )),
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
async def test_get_files():
    from seplis_play_server.scanners import Episode_scan
    scanner = Episode_scan(scan_path='/', cleanup_mode=True, make_thumbnails=False)

    with mock.patch('subprocess.Popen') as mock_popen:
        with mock.patch('os.path.exists') as mock_path_exists:
            mock_path_exists.return_value = True
            mock_popen().stdout.read.return_value = '{"metadata": "test"}'
            mock_popen().stderr.read.return_value = None
            
            m = await scanner.get_metadata('somefile.mp4')
            assert m == {'metadata': 'test'}


@pytest.mark.asyncio
@respx.mock
async def test_series_id_lookup(play_db_test: Database):
    from seplis_play_server.scanners import Episode_scan
    scanner = Episode_scan(scan_path='/', cleanup_mode=True, make_thumbnails=False)

    respx.get('/2/search').mock(return_value=httpx.Response(200, json=[{
        'id': 1,
        'title': 'Test series',
    }]))

    # test that a series we haven't searched for is not in the db
    assert None == await scanner.series_id.db_lookup('test series')

    # search for the series
    assert 1 == await scanner.series_id.lookup('test series')

    # the result should now be stored in the database
    assert 1 == await scanner.series_id.db_lookup('test series')


@pytest.mark.asyncio
async def test_save_item(play_db_test: Database):
    from seplis_play_server.scanners import Episode_scan
    from seplis_play_server.scanners.episodes import (
        Episode_scan, 
        Parsed_episode_season, 
        Parsed_episode_air_date, Parsed_episode_number,
    )
    scanner = Episode_scan(scan_path='/', cleanup_mode=True, make_thumbnails=False)
    scanner.get_file_modified_time = mock.MagicMock(return_value=datetime(2014, 11, 14, 21, 25, 58))
    scanner.get_metadata = mock.AsyncMock(return_value={
        'some': 'data',
    })
    episodes = []
    episodes.append((Parsed_episode_season(
        series_id=1,
        file_title='ncis',
        season=1,
        episode=2,
        number=2,
    ), '/ncis/ncis.s01e02.mp4'))
    episodes.append((Parsed_episode_air_date(
        series_id=1,
        file_title='ncis',
        air_date='2014-11-14',
        number=3,
    ), '/ncis/ncis.2014-11-14.mp4'))
    episodes.append((Parsed_episode_number(
        series_id=1,
        file_title='ncis',
        number=4,
    ), '/ncis/ncis.4.mp4'))
    # episodes saved
    for episode in episodes:
        await scanner.save_item(episode[0], episode[1])

    # check that metadata was called for all the episodes.
    # if metadata i getting called the episode will be 
    # inserted/updated in the db.
    scanner.get_metadata.assert_has_calls([
        mock.call('/ncis/ncis.s01e02.mp4'),
        mock.call('/ncis/ncis.2014-11-14.mp4'),
        mock.call('/ncis/ncis.4.mp4'),
    ])

    # check that calling `save_items` again does not result
    # in a update since the `modified_time` has not changed for
    # any of them.      
    scanner.get_metadata.reset_mock()
    for episode in episodes:
        await scanner.save_item(episode[0], episode[1])
    scanner.get_metadata.assert_has_calls([])

    # check that changing the `modified_time` will result in the
    # episode getting updated in the db.        
    scanner.get_metadata.reset_mock()
    scanner.get_file_modified_time.return_value = datetime(2014, 11, 15, 21, 25, 58)
    await scanner.save_item(episodes[1][0], episodes[1][1])
    scanner.get_metadata.assert_has_calls(
        [mock.call('/ncis/ncis.2014-11-14.mp4')],
    )

    async with play_db_test.session() as session:
        r = await session.scalars(sa.select(models.Episode))
        r = r.all()
        assert len(r) == 3

    await scanner.delete_path(episodes[0][1])

    async with play_db_test.session() as session:
        r = await session.scalars(sa.select(models.Episode))
        r = r.all()
        assert len(r) == 2


@pytest.mark.asyncio
@respx.mock
async def test_episode_number_lookup(play_db_test: Database):
    from seplis_play_server.scanners import Episode_scan
    from seplis_play_server.scanners.episodes import (
        Episode_scan, 
        Parsed_episode_season, 
        Parsed_episode_air_date, Parsed_episode_number,
    )
    scanner = Episode_scan(scan_path='/', cleanup_mode=True, make_thumbnails=False)

    # test parsed episode season
    respx.get('/2/series/1/episodes', params={'season': '1', 'episode': '2'}).mock(
        return_value=httpx.Response(200, 
            json=schemas.Page_cursor_result[schemas.Episode](
                items=[schemas.Episode(number=2)]
            ).dict())
    )
    episode = Parsed_episode_season(
        series_id=1,
        file_title='NCIS',
        season=1,
        episode=2,
    )
    assert None == await scanner.episode_number.db_lookup(episode)
    assert 2 == await scanner.episode_number.lookup(episode)
    assert 2 == await scanner.episode_number.db_lookup(episode)
    

    # test parsed episode air_date
    respx.get('/2/series/1/episodes', params={'air_date': '2014-11-14'}).mock(
        return_value=httpx.Response(200, 
            json=schemas.Page_cursor_result[schemas.Episode](
                items=[schemas.Episode(number=3)]
            ).dict())
    )
    episode = Parsed_episode_air_date(
        series_id=1,
        file_title='NCIS',
        air_date='2014-11-14',
    )
    assert None == await scanner.episode_number.db_lookup(episode)
    assert 3 == await scanner.episode_number.lookup(episode)
    assert 3 == await scanner.episode_number.db_lookup(episode)
    

    # test parsed episode number
    episode = Parsed_episode_number(
        series_id=1,
        file_title='NCIS',
        number=4,
    )
    assert await scanner.episode_number_lookup(episode)
    # there is no reason to have a lookup record for an
    # episode that already contains the episode number.
    with pytest.raises(Exception):
        await scanner.episode_number.db_lookup(episode)
    assert 4 == await scanner.episode_number.lookup(episode)


@pytest.mark.asyncio
async def test_parse_episodes(play_db_test: Database):
    from seplis_play_server.scanners import Episode_scan
    from seplis_play_server.scanners.episodes import (
        Episode_scan, 
        Parsed_episode_season, 
        Parsed_episode_air_date, Parsed_episode_number,
    )
    scanner = Episode_scan(scan_path='/', cleanup_mode=True, make_thumbnails=False)
    
    # Normal
    path = '/Alpha House/Alpha.House.S02E01.The.Love.Doctor.720p.AI.WEBRip.DD5.1.x264-NTb.mkv'
    info = scanner.parse(path)
    assert isinstance(info, Parsed_episode_season)
    assert info.file_title == 'alpha.house'
    assert info.season == 2
    assert info.episode == 1

    # Anime
    path = '/Naruto/[HorribleSubs] Naruto Shippuuden - 379 [1080p].mkv'
    info = scanner.parse(path)
    assert isinstance(info, Parsed_episode_number)

    assert info.file_title == 'naruto shippuuden'
    assert info.number, 379

    path = '/Naruto Shippuuden/Naruto Shippuuden.426.720p.mkv'
    info = scanner.parse(path)
    assert isinstance(info, Parsed_episode_number)
    assert info.file_title, 'naruto shippuuden'
    assert info.number, 426

    # Air date
    path = '/The Daily series/The.Daily.series.2014.06.03.Ricky.Gervais.HDTV.x264-D0NK.mp4'
    info = scanner.parse(path)
    assert isinstance(info, Parsed_episode_air_date)
    assert info.file_title, 'the.daily.series'
    assert info.air_date, '2014-06-03'

    # Double episode
    path = 'Star Wars Resistance.S01E01-E02.720p webdl h264 aac.mkv'
    info = scanner.parse(path)
    assert isinstance(info, Parsed_episode_season)
    assert info.file_title, 'star wars resistance'
    assert info.season, 1
    assert info.episode, 1
    
    path = 'Boruto Naruto Next Generations (2017).6.1080p h265.mkv'
    info = scanner.parse(path)
    assert isinstance(info, Parsed_episode_number)
    assert info.file_title, 'boruto naruto next generations (2017)'
    assert info.number, 6


if __name__ == '__main__':
    run_file(__file__)