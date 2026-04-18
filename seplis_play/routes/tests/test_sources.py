import asyncio

from pytest import MonkeyPatch

import seplis_play.routes.sources_routes as sources_routes
from seplis_play.routes.sources_routes import resolution_text
from seplis_play.testbase import run_file


def test_resolution_text() -> None:
    assert resolution_text(640, 480) == '480p'
    assert resolution_text(1280, 720) == '720p'
    assert resolution_text(1920, 1080) == '1080p'
    assert resolution_text(3832, 1600) == '4K'
    assert resolution_text(7680, 4320) == '8K'


def test_get_sources_route_exposes_media_type(monkeypatch: MonkeyPatch) -> None:
    async def noop_fill_external_subtitles(filename: str, subtitles: list) -> None:
        return None

    monkeypatch.setattr(
        sources_routes, 'fill_external_subtitles', noop_fill_external_subtitles
    )

    sources = [
        {
            'streams': [
                {
                    'index': 0,
                    'codec_name': 'h264',
                    'codec_type': 'video',
                    'profile': 'High',
                    'codec_tag_string': 'avc1',
                    'width': 1920,
                    'height': 1080,
                    'pix_fmt': 'yuv420p',
                    'level': 40,
                },
                {
                    'index': 1,
                    'codec_name': 'aac',
                    'codec_type': 'audio',
                    'profile': 'LC',
                    'disposition': {'default': 1},
                },
            ],
            'format': {
                'filename': '/tmp/movie.mp4',
                'format_name': 'mp4',
                'duration': '10.0',
                'size': '1000',
                'bit_rate': '800',
            },
        }
    ]

    response = asyncio.run(sources_routes.get_sources_route(sources=sources))

    assert response[0].media_type == 'video/mp4; codecs="avc1.640028, mp4a.40.2"'


if __name__ == '__main__':
    run_file(__file__)
