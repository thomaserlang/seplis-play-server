import asyncio

from seplis_play.routes.request_media_routes import request_media_route
from seplis_play.schemas.source_metadata_schemas import SourceMetadata
from seplis_play.transcoding.base_transcoder import BaseTranscoder, sessions
from seplis_play.transcoding.transcode_decision_schema import (
    BlockerCode,
    DecisionScope,
    PlaybackMethod,
    StreamAction,
    StreamKind,
)
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


def test_transcoder_collects_compact_transcode_blockers() -> None:
    sessions.clear()
    settings = TranscodeSettings(
        play_id='play-id',
        session='a' * 32,
        supported_hdr_formats=[],
        supported_video_containers=['mp4'],
        supported_video_codecs=['h264'],
        supported_audio_codecs=['aac'],
    )

    transcoder = BaseTranscoder(settings=settings, metadata=TRANSCODE_METADATA)

    assert transcoder.transcode_decision.method is PlaybackMethod.TRANSCODE
    assert transcoder.transcode_decision.direct_play.supported is False
    assert transcoder.transcode_decision.required is True
    assert transcoder.transcode_decision.video.action is StreamAction.TRANSCODE
    assert transcoder.transcode_decision.audio.action is StreamAction.TRANSCODE
    assert transcoder.transcode_decision.video.blockers[0].code is (
        BlockerCode.UNSUPPORTED_CODEC
    )
    assert transcoder.transcode_decision.audio.blockers[0].code is (
        BlockerCode.VIDEO_TRANSCODE_REQUIRES_AUDIO_TRANSCODE
    )
    direct_play_blocker_codes = [
        blocker.code for blocker in transcoder.transcode_decision.direct_play.blockers
    ]
    assert direct_play_blocker_codes == [
        BlockerCode.UNSUPPORTED_CODEC,
    ]


def test_direct_play_reports_one_blocker_for_audio_codec_mismatch() -> None:
    sessions.clear()
    settings = TranscodeSettings(
        play_id='play-id',
        session='c' * 32,
        supported_hdr_formats=[],
        supported_video_containers=['mp4'],
        supported_video_codecs=['h264'],
        supported_audio_codecs=['opus'],
    )

    transcoder = BaseTranscoder(settings=settings, metadata=DIRECT_PLAY_METADATA)

    assert transcoder.transcode_decision.direct_play.supported is False
    assert len(transcoder.transcode_decision.direct_play.blockers) == 1
    blocker = transcoder.transcode_decision.direct_play.blockers[0]
    assert blocker.code is BlockerCode.UNSUPPORTED_CODEC
    assert blocker.scope is DecisionScope.AUDIO
    assert blocker.stream is StreamKind.AUDIO


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
    assert response.hls_url.startswith('/hls/media.m3u8?')
    assert f'session={session}' in response.hls_url
    assert 'hls_include_all_subtitles=False' in response.hls_url
    assert response.transcode_decision
    assert response.model_dump(mode='json')['transcode_decision'] == {
        'method': 'direct_play',
        'target_format': 'hls',
        'required': False,
        'direct_play': {
            'supported': True,
            'blockers': [],
        },
        'video': {
            'kind': 'video',
            'action': 'copy',
            'source_codec': 'h264',
            'target_codec': 'h264',
            'blockers': [],
        },
        'audio': {
            'kind': 'audio',
            'action': 'copy',
            'source_codec': 'aac',
            'target_codec': 'aac',
            'blockers': [],
        },
    }
