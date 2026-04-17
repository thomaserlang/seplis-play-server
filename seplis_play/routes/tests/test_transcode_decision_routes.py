import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient

from seplis_play.dependencies import get_metadata
from seplis_play.routes import request_media_routes, transcode_decision_routes
from seplis_play.ffmpeg.ffmpeg_runner import FFmpegRunner
from seplis_play.transcoding.base_transcoder import SessionModel, Transcoder, sessions
from seplis_play.transcoding.transcode_settings_schema import TranscodeSettings


TRANSCODE_METADATA = {
    'streams': [
        {
            'index': 0,
            'codec_name': 'hevc',
            'codec_type': 'video',
            'codec_tag_string': '[0][0][0][0]',
            'width': 1920,
            'height': 1080,
            'pix_fmt': 'yuv420p10le',
            'r_frame_rate': '24000/1001',
        },
        {
            'index': 1,
            'codec_name': 'aac',
            'codec_type': 'audio',
            'sample_rate': '48000',
            'channels': 6,
            'disposition': {'default': 1},
        },
    ],
    'format': {
        'filename': '/tmp/movie.mkv',
        'format_name': 'matroska,webm',
        'duration': '3486.590000',
        'bit_rate': '6294815',
    },
    'keyframes': ['0.000000', '6.715000'],
}

DIRECT_PLAY_METADATA = {
    'streams': [
        {
            'index': 0,
            'codec_name': 'h264',
            'codec_type': 'video',
            'codec_tag_string': 'avc1',
            'width': 1920,
            'height': 1080,
            'pix_fmt': 'yuv420p',
            'r_frame_rate': '24000/1001',
        },
        {
            'index': 1,
            'codec_name': 'aac',
            'codec_type': 'audio',
            'sample_rate': '48000',
            'channels': 2,
            'disposition': {'default': 1},
        },
    ],
    'format': {
        'filename': '/tmp/movie.mp4',
        'format_name': 'mp4',
        'duration': '3486.590000',
        'bit_rate': '2500000',
    },
    'keyframes': ['0.000000', '6.715000'],
}


def test_transcoder_collects_human_readable_transcode_reasons() -> None:
    sessions.clear()
    settings = TranscodeSettings(
        play_id='play-id',
        session='a' * 32,
        supported_hdr_formats=[],
        supported_video_containers=['mp4'],
        supported_video_codecs=['h264'],
        supported_audio_codecs=['aac'],
    )

    transcoder = Transcoder(settings=settings, metadata=TRANSCODE_METADATA)

    assert transcoder.transcode_decision.video_transcode_required is True
    assert transcoder.transcode_decision.audio_transcode_required is True
    assert transcoder.transcode_decision.transcode_required is True
    assert transcoder.transcode_decision.video_copy.reasons == [
        'Input codec not supported by client: hevc'
    ]
    assert transcoder.transcode_decision.audio_copy.reasons == [
        'Audio copy disabled while video is transcoded to avoid sync issues'
    ]
    assert transcoder.transcode_decision.direct_play.reasons == [
        'Direct play requires video copy',
        'Input codec not supported by client: hevc',
    ]


def test_request_media_exposes_transcode_decision_by_session() -> None:
    sessions.clear()
    app = FastAPI()
    app.include_router(request_media_routes.router)
    app.include_router(transcode_decision_routes.router)

    async def _get_metadata(play_id: str, source_index: int) -> dict:
        assert play_id == 'play-id'
        assert source_index == 0
        return DIRECT_PLAY_METADATA

    app.dependency_overrides[get_metadata] = _get_metadata
    client = TestClient(app)

    session = 'b' * 32
    response = client.get(
        '/request-media',
        params={
            'play_id': 'play-id',
            'session': session,
            'source_index': 0,
            'supported_video_codecs': 'h264',
            'supported_audio_codecs': 'aac',
            'supported_video_containers': 'mp4',
        },
    )

    assert response.status_code == 200
    assert response.json()['can_direct_play'] is True
    assert response.json()['transcode_decision_url'] == (
        f'/transcode-decision/{session}'
    )

    decision = Transcoder(
        settings=TranscodeSettings(
            play_id='play-id',
            session=session,
            supported_video_codecs=['h264'],
            supported_audio_codecs=['aac'],
            supported_video_containers=['mp4'],
        ),
        metadata=DIRECT_PLAY_METADATA,
    ).transcode_decision
    loop = asyncio.new_event_loop()
    try:
        sessions[session] = SessionModel(
            ffmpeg_runner=FFmpegRunner(),
            call_later=loop.call_later(60, lambda: None),
            transcode_decision=decision,
        )
        decision_response = client.get(f'/transcode-decision/{session}')
    finally:
        sessions[session].call_later.cancel()
        del sessions[session]
        loop.close()

    assert decision_response.status_code == 200
    assert decision_response.json() == {
        'session': session,
        'video_copy': {
            'allowed': True,
            'reasons': ['Video can be copied'],
        },
        'audio_copy': {
            'allowed': True,
            'reasons': ['Audio can be copied, codec: aac'],
        },
        'direct_play': {
            'allowed': True,
            'reasons': ['Direct play is supported'],
        },
        'video_transcode_required': False,
        'audio_transcode_required': False,
        'transcode_required': False,
    }


def test_transcode_decision_route_returns_404_for_unknown_session() -> None:
    sessions.clear()
    app = FastAPI()
    app.include_router(transcode_decision_routes.router)
    client = TestClient(app)

    response = client.get('/transcode-decision/missing-session')

    assert response.status_code == 404
    assert response.json() == {'detail': 'Unknown session'}
