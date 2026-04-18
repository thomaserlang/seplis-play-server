import asyncio

from seplis_play.routes.request_media_routes import request_media_route
from seplis_play.schemas.source_metadata_schemas import SourceMetadata
from seplis_play.transcoding.base_transcoder import Transcoder, sessions
from seplis_play.transcoding.transcode_settings_schema import TranscodeSettings

TRANSCODE_METADATA: SourceMetadata = {
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
        'size': '2743430123',
        'bit_rate': '6294815',
    },
    'keyframes': ['0.000000', '6.715000'],
}

DIRECT_PLAY_METADATA: SourceMetadata = {
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
        'size': '2743430123',
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
        'Unsupported video codec (hevc; client: h264)'
    ]
    assert transcoder.transcode_decision.audio_copy.reasons == [
        'Audio copy disabled during video transcode '
        '(video: hevc -> h264, audio: aac -> aac)'
    ]
    assert transcoder.transcode_decision.direct_play.reasons == [
        'Direct play: unsupported video codec (hevc)',
        'Unsupported video codec (hevc; client: h264)',
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
    assert response.transcode_decision
    assert response.transcode_decision.model_dump() == {
        'session': session,
        'video_copy': {
            'supported': True,
            'reasons': ['Video copy: h264'],
        },
        'audio_copy': {
            'supported': True,
            'reasons': ['Audio copy: aac'],
        },
        'direct_play': {
            'supported': True,
            'reasons': ['Direct play (container: mp4, video: h264, audio: aac)'],
        },
        'video_transcode_required': False,
        'audio_transcode_required': False,
        'transcode_required': False,
    }
