from seplis_play.routes.sources_routes import resolution_text
from seplis_play.testbase import run_file


def test_resolution_text() -> None:
    assert resolution_text(640, 480) == '480p'
    assert resolution_text(1280, 720) == '720p'
    assert resolution_text(1920, 1080) == '1080p'
    assert resolution_text(3832, 1600) == '4K'
    assert resolution_text(7680, 4320) == '8K'


if __name__ == '__main__':
    run_file(__file__)
