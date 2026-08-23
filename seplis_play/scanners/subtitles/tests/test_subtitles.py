import os
import tempfile

import pytest
import respx
import sqlalchemy as sa

from seplis_play.database import Database
from seplis_play.scanners.subtitles.subtitle_models import MExternalSubtitle
from seplis_play.testbase import run_file


@pytest.mark.asyncio
@respx.mock
async def test_subtitles(play_db_test: Database) -> None:
    from seplis_play.scanners import SubtitleScan

    filenames = [
        (
            'Blue Exorcist (2011) - S01E01 - 001'
            ' [HDTV-1080p][10bit][x265][Opus 2.0][EN+JA].en.forced.srt'
        ),
        (
            'Blue Exorcist (2011) - S01E01 - 001'
            ' [HDTV-1080p][10bit][x265][Opus 2.0][EN+JA].en.srt'
        ),
        'Breaking Bad (2008).S01E01.1080p bluray h265.da.srt',
        'Breaking Bad (2008).S01E01.1080p bluray h265.en.forced.srt',
        'Breaking Bad (2008).S01E01.1080p bluray h265.en.sdh.srt',
        'Breaking Bad (2008).S01E01.1080p bluray h265.en.srt',
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        paths = []
        for name in filenames:
            path = os.path.join(tmpdir, name)
            open(path, 'w').close()
            paths.append(path)

        scanner = SubtitleScan(scan_path=tmpdir, cleanup_mode=True, make_thumbnails=False)
        await scanner.scan()

        async with play_db_test.session() as session:
            r = await session.scalars(
                sa.select(MExternalSubtitle).order_by(MExternalSubtitle.id)
            )
            r = list(r)

            assert r[0].path == paths[0]
            assert r[0].language == 'en'
            assert not r[0].default
            assert r[0].forced
            assert r[0].type == 'srt'
            assert not r[0].sdh

            assert r[1].path == paths[1]
            assert r[1].language == 'en'
            assert not r[1].default
            assert not r[1].forced
            assert r[1].type == 'srt'
            assert not r[1].sdh

            assert r[2].path == paths[2]
            assert r[2].language == 'da'
            assert not r[2].default
            assert not r[2].forced
            assert r[2].type == 'srt'
            assert not r[2].sdh

            assert r[3].path == paths[3]
            assert r[3].language == 'en'
            assert not r[3].default
            assert r[3].forced
            assert r[3].type == 'srt'
            assert not r[3].sdh

            assert r[4].path == paths[4]
            assert r[4].language == 'en'
            assert not r[4].default
            assert not r[4].forced
            assert r[4].type == 'srt'
            assert r[4].sdh

            assert r[5].path == paths[5]
            assert r[5].language == 'en'
            assert not r[5].default
            assert not r[5].forced
            assert r[5].type == 'srt'
            assert not r[5].sdh


if __name__ == '__main__':
    run_file(__file__)
