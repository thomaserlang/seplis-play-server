import asyncio

from fastapi import HTTPException

from seplis_play.ffmpeg.ffmpeg_runner import FFmpegRunner
from seplis_play.routes.request_media_routes import request_media_route
from seplis_play.routes.transcode_decision_routes import get_transcode_decision_route
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
            'profile': 'High',
            'codec_tag_string': 'avc1',
            'width': 1920,
            'height': 1080,
            'pix_fmt': 'yuv420p',
            'level': 40,
            'r_frame_rate': '24000/1001',
        },
        {
            'index': 1,
            'codec_name': 'aac',
            'codec_type': 'audio',
            'profile': 'LC',
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
    session = 'b' * 32
    response = asyncio.run(
        request_media_route(
            source_index=0,
            settings=TranscodeSettings(
                play_id='play-id',
                session=session,
                source_index=0,
                supported_hdr_formats=[],
                supported_video_codecs=['h264'],
                supported_audio_codecs=['aac'],
                supported_video_containers=['mp4'],
            ),
            metadata=DIRECT_PLAY_METADATA,
        )
    )

    assert response.can_direct_play is True
    assert response.direct_play_media_type == (
        'video/mp4; codecs="avc1.640028, mp4a.40.2"'
    )
    assert response.video_media_type == 'video/mp4; codecs="avc1.640028"'
    assert response.audio_media_type == 'audio/mp4; codecs="mp4a.40.2"'
    assert response.transcode_decision

    decision = Transcoder(
        settings=TranscodeSettings(
            play_id='play-id',
            session=session,
            supported_hdr_formats=[],
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
        decision_response = asyncio.run(get_transcode_decision_route(session))
    finally:
        sessions[session].call_later.cancel()
        del sessions[session]
        loop.close()

    assert decision_response.model_dump() == {
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
    try:
        asyncio.run(get_transcode_decision_route('missing-session'))
    except HTTPException as exc:
        assert exc.status_code == 404
        assert exc.detail == 'Unknown session'
    else:
        raise AssertionError('Expected HTTPException')
