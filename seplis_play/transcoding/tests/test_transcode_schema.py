from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import RootModel

from seplis_play.transcoding.transcode_settings_schema import TranscodeSettings


def _create_client() -> TestClient:
    app = FastAPI()

    @app.get('/transcode')
    def transcode_settings(
        settings: Annotated[TranscodeSettings, Depends()],
    ) -> dict:
        return RootModel[TranscodeSettings](settings).model_dump(mode='json')

    return TestClient(app)


def test_transcode_settings_are_parsed_like_fastapi_query_params() -> None:
    client = _create_client()

    response = client.get(
        '/transcode',
        params=[
            ('play_id', 'play-id'),
            ('session', 'a' * 32),
            ('supported_hdr_formats', 'hdr10'),
            ('supported_hdr_formats', 'dovi'),
            ('supported_audio_codecs', 'aac'),
            ('supported_audio_codecs', 'opus'),
            ('supported_video_containers', 'mp4'),
            ('supported_video_containers', 'webm'),
            ('supported_video_codecs', 'h264'),
            ('supported_video_codecs', 'av1'),
            ('supported_video_color_bit_depth', '10'),
            ('start_time', '0'),
            ('max_width', '1920'),
            ('client_can_switch_audio_track', 'true'),
            ('force_transcode', 'true'),
        ],
    )

    assert response.status_code == 200
    assert response.json() == {
        'play_id': 'play-id',
        'session': 'a' * 32,
        'supported_hdr_formats': ['hdr10', 'dovi'],
        'supported_audio_codecs': ['aac', 'opus'],
        'supported_video_containers': ['mp4', 'webm'],
        'source_index': 0,
        'supported_video_codecs': ['h264', 'av1'],
        'format': 'hls',
        'transcode_video_codec': 'h264',
        'transcode_audio_codec': 'aac',
        'supported_video_color_bit_depth': 10,
        'start_time': '0',
        'start_segment': None,
        'audio_lang': None,
        'hls_include_all_subtitles': False,
        'hls_subtitle_lang': None,
        'hls_subtitle_offset': None,
        'max_audio_channels': None,
        'max_width': 1920,
        'max_video_bitrate': None,
        'client_can_switch_audio_track': True,
        'force_transcode': True,
    }


def test_transcode_settings_list_fields_accept_comma_separated_query_params() -> None:
    client = _create_client()

    response = client.get(
        '/transcode',
        params=[
            ('play_id', 'play-id'),
            ('session', 'a' * 32),
            ('supported_hdr_formats', 'hdr10,dovi'),
            ('supported_audio_codecs', 'aac,opus'),
            ('supported_video_containers', 'mp4,webm'),
            ('supported_video_codecs', 'h264,av1'),
        ],
    )

    assert response.status_code == 200
    assert response.json()['supported_hdr_formats'] == ['hdr10', 'dovi']
    assert response.json()['supported_audio_codecs'] == ['aac', 'opus']
    assert response.json()['supported_video_containers'] == ['mp4', 'webm']
    assert response.json()['supported_video_codecs'] == ['h264', 'av1']


def test_transcode_settings_include_subtitles_defaults_to_false_and_can_be_enabled() -> (
    None
):
    client = _create_client()

    default_response = client.get(
        '/transcode',
        params={
            'play_id': 'play-id',
            'session': 'a' * 32,
        },
    )
    enabled_response = client.get(
        '/transcode',
        params={
            'play_id': 'play-id',
            'session': 'b' * 32,
            'hls_include_all_subtitles': 'true',
        },
    )

    assert default_response.status_code == 200
    assert default_response.json()['hls_include_all_subtitles'] is False
    assert enabled_response.status_code == 200
    assert enabled_response.json()['hls_include_all_subtitles'] is True


def test_transcode_settings_validation_errors_match_fastapi_response() -> None:
    client = _create_client()

    response = client.get(
        '/transcode',
        params={
            'play_id': '',
            'session': 'short',
        },
    )

    assert response.status_code == 422
    assert response.json()['detail'] == [
        {
            'type': 'string_too_short',
            'loc': ['query', 'play_id'],
            'msg': 'String should have at least 1 character',
            'input': '',
            'ctx': {'min_length': 1},
        },
        {
            'type': 'string_too_short',
            'loc': ['query', 'session'],
            'msg': 'String should have at least 32 characters',
            'input': 'short',
            'ctx': {'min_length': 32},
        },
    ]


def test_transcode_settings_rejects_invalid_non_literal_list_values() -> None:
    client = _create_client()

    response = client.get(
        '/transcode',
        params=[
            ('play_id', 'play-id'),
            ('session', 'a' * 32),
            ('supported_audio_codecs', 'aac,Opus'),
            ('supported_video_containers', 'mp4,web m'),
            ('supported_video_codecs', 'h264,av1!'),
        ],
    )

    assert response.status_code == 422
    assert response.json()['detail'] == [
        {
            'type': 'string_pattern_mismatch',
            'loc': ['query', 'supported_audio_codecs', 1],
            'msg': "String should match pattern '^[a-z0-9][a-z0-9._-]*$'",
            'input': 'Opus',
            'ctx': {'pattern': '^[a-z0-9][a-z0-9._-]*$'},
        },
        {
            'type': 'string_pattern_mismatch',
            'loc': ['query', 'supported_video_containers', 1],
            'msg': "String should match pattern '^[a-z0-9][a-z0-9._-]*$'",
            'input': 'web m',
            'ctx': {'pattern': '^[a-z0-9][a-z0-9._-]*$'},
        },
        {
            'type': 'string_pattern_mismatch',
            'loc': ['query', 'supported_video_codecs', 1],
            'msg': "String should match pattern '^[a-z0-9][a-z0-9._-]*$'",
            'input': 'av1!',
            'ctx': {'pattern': '^[a-z0-9][a-z0-9._-]*$'},
        },
    ]


def test_fastapi_rejects_some_raw_query_values_before_dataclass_validators_run() -> None:
    client = _create_client()

    response = client.get(
        '/transcode',
        params=[
            ('play_id', 'play-id'),
            ('session', 'a' * 32),
            ('supported_video_codecs', 'h264,av1'),
            ('supported_video_color_bit_depth', ''),
            ('start_time', ''),
            ('start_segment', ''),
            ('max_audio_channels', ''),
            ('max_video_bitrate', ''),
        ],
    )

    assert response.status_code == 422
    assert response.json()['detail'] == [
        {
            'type': 'int_parsing',
            'loc': ['query', 'supported_video_color_bit_depth'],
            'msg': (
                'Input should be a valid integer, unable to parse string as an integer'
            ),
            'input': '',
        },
        {
            'type': 'decimal_parsing',
            'loc': ['query', 'start_time'],
            'msg': 'Input should be a valid decimal',
            'input': '',
        },
        {
            'type': 'int_parsing',
            'loc': ['query', 'start_segment'],
            'msg': (
                'Input should be a valid integer, unable to parse string as an integer'
            ),
            'input': '',
        },
        {
            'type': 'int_parsing',
            'loc': ['query', 'max_audio_channels'],
            'msg': (
                'Input should be a valid integer, unable to parse string as an integer'
            ),
            'input': '',
        },
        {
            'type': 'int_parsing',
            'loc': ['query', 'max_video_bitrate'],
            'msg': (
                'Input should be a valid integer, unable to parse string as an integer'
            ),
            'input': '',
        },
    ]
