import pytest
import respx
import sqlalchemy as sa
from unittest import mock
from seplis_play_server.testbase import run_file, play_db_test
from seplis_play_server.database import Database
from seplis_play_server import models, logger


@pytest.mark.asyncio
@respx.mock
async def test_subtitles(play_db_test: Database):
    from seplis_play_server.scanners import Subtitle_scan
    scanner = Subtitle_scan(scan_path='/', cleanup_mode=True, make_thumbnails=False)

    scanner.get_files = mock.MagicMock(return_value=[
        'Breaking Bad (2008).S01E01.1080p bluray h265.da.srt',
        'Breaking Bad (2008).S01E01.1080p bluray h265.en.srt',
        'Breaking Bad (2008).S01E01.1080p bluray h265.en.forced.srt',
        'Breaking Bad (2008).S01E01.1080p bluray h265.en.sdh.srt',
        'Breaking Bad (2008).S01E01.1080p bluray h265.en.default.srt',
        'Blue Exorcist (2011) - S01E01 - 001 [HDTV-1080p][10bit][x265][Opus 2.0][EN+JA].en.srt',
        'Blue Exorcist (2011) - S01E01 - 001 [HDTV-1080p][10bit][x265][Opus 2.0][EN+JA].en.forced.srt',
    ])
    await scanner.scan()

    async with play_db_test.session() as session:
        r = await session.scalars(sa.select(models.External_subtitle))
        r = list(r)
        assert r[0].path == 'Breaking Bad (2008).S01E01.1080p bluray h265.da.srt'
        assert r[0].language == 'da'
        assert r[0].default == False
        assert r[0].forced == False
        assert r[0].type == 'srt'
        assert r[0].sdh == False

        assert r[1].path == 'Breaking Bad (2008).S01E01.1080p bluray h265.en.srt'
        assert r[1].language == 'en'
        assert r[1].default == False
        assert r[1].forced == False
        assert r[1].type == 'srt'
        assert r[1].sdh == False

        assert r[2].path == 'Breaking Bad (2008).S01E01.1080p bluray h265.en.forced.srt'
        assert r[2].language == 'en'
        assert r[2].default == False
        assert r[2].forced == True
        assert r[2].type == 'srt'
        assert r[2].sdh == False

        assert r[3].path == 'Breaking Bad (2008).S01E01.1080p bluray h265.en.sdh.srt'
        assert r[3].language == 'en'
        assert r[3].default == False
        assert r[3].forced == False
        assert r[3].type == 'srt'
        assert r[3].sdh == True
        
        assert r[4].path == 'Breaking Bad (2008).S01E01.1080p bluray h265.en.default.srt'
        assert r[4].language == 'en'
        assert r[4].default == True
        assert r[4].forced == False
        assert r[4].type == 'srt'
        assert r[4].sdh == False
        
        assert r[5].path == 'Blue Exorcist (2011) - S01E01 - 001 [HDTV-1080p][10bit][x265][Opus 2.0][EN+JA].en.srt'
        assert r[5].language == 'en'
        assert r[5].default == False
        assert r[5].forced == False
        assert r[5].type == 'srt'
        assert r[5].sdh == False

        assert r[6].path == 'Blue Exorcist (2011) - S01E01 - 001 [HDTV-1080p][10bit][x265][Opus 2.0][EN+JA].en.forced.srt'
        assert r[6].language == 'en'
        assert r[6].default == False
        assert r[6].forced == True
        assert r[6].type == 'srt'
        assert r[6].sdh == False
        

if __name__ == '__main__':
    run_file(__file__)