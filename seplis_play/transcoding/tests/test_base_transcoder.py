from uuid import uuid4

from seplis_play.schemas.source_metadata_schemas import SourceMetadata
from seplis_play.transcoding.base_transcoder import (
    BaseTranscoder,
    summarize_transcode_decision,
)
from seplis_play.transcoding.transcode_settings_schema import TranscodeSettings


def test_client_audio_track_switch_unsupported() -> None:
    settings = TranscodeSettings(
        play_id='a',
        session=uuid4().hex,
        supported_hdr_formats=[],
        audio_lang='dan:2',
        supported_video_containers=['mp4'],
        supported_video_codecs=['h264', 'hevc'],
        supported_audio_codecs=['aac'],
        transcode_video_codec='h264',
        transcode_audio_codec='aac',
        format='hls',
    )
    metadata: SourceMetadata = {
        'streams': [
            {
                'index': 0,
                'codec_name': 'hevc',
                'profile': 'Main 10',
                'level': 120,
                'codec_type': 'video',
                'codec_tag_string': 'hvc1',
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
                'channels': 2,
                'tags': {
                    'language': 'eng',
                    'title': 'English',
                },
                'disposition': {
                    'default': 1,
                },
            },
            {
                'index': 2,
                'codec_name': 'aac',
                'codec_type': 'audio',
                'sample_rate': '48000',
                'channels': 6,
                'tags': {
                    'language': 'dan',
                    'title': 'Danish 5.1',
                },
            },
        ],
        'format': {
            'format_name': 'mp4',
            'filename': '/tmp/movie.mp4',
            'duration': '120.000000',
            'size': '1000000',
            'bit_rate': '2500000',
        },
        'keyframes': ['0.000000', '6.000000'],
    }

    transcoder = BaseTranscoder(settings, metadata)

    assert transcoder.direct_play_decision.supported is False, (
        summarize_transcode_decision(transcoder.transcode_decision)
    )
    assert (
        transcoder.direct_play_decision.blockers[0].code
        == 'client_audio_track_switch_unsupported'
    )

    settings = TranscodeSettings(
        play_id='a',
        session=uuid4().hex,
        supported_hdr_formats=[],
        audio_lang='eng:0',
        supported_video_containers=['mp4'],
        supported_video_codecs=['h264', 'hevc'],
        supported_audio_codecs=['aac'],
        transcode_video_codec='h264',
        transcode_audio_codec='aac',
        format='hls',
    )
    transcoder = BaseTranscoder(settings, metadata)
    assert transcoder.direct_play_decision.supported is True, (
        summarize_transcode_decision(transcoder.transcode_decision)
    )
