import asyncio
from typing import cast
from uuid import uuid4

import pytest

from seplis_play import config
from seplis_play.schemas.source_metadata_schemas import SourceMetadata
from seplis_play.testbase import run_file
from seplis_play.transcoding.hls_transcoder import HlsTranscoder
from seplis_play.transcoding.transcode_settings_schema import TranscodeSettings


def test_hls() -> None:
    settings = TranscodeSettings(
        play_id='a',
        session=uuid4().hex,
        supported_hdr_formats=[],
        supported_video_containers=['mp4'],
        supported_video_codecs=['h264'],
        supported_audio_codecs=['aac'],
        transcode_video_codec='h264',
        transcode_audio_codec='aac',
        format='hls',
    )
    metadata = cast(
        SourceMetadata,
        {
            'streams': [
                {
                    'index': 0,
                    'codec_name': 'hevc',
                    'codec_long_name': 'H.265 / HEVC (High Efficiency Video Coding)',
                    'profile': 'Main 10',
                    'codec_type': 'video',
                    'codec_tag_string': '[0][0][0][0]',
                    'codec_tag': '0x0000',
                    'width': 1920,
                    'height': 1080,
                    'coded_width': 1920,
                    'coded_height': 1080,
                    'has_b_frames': 2,
                    'sample_aspect_ratio': '1:1',
                    'display_aspect_ratio': '16:9',
                    'pix_fmt': 'yuv420p10le',
                    'level': 120,
                    'color_range': 'tv',
                    'chroma_location': 'left',
                    'r_frame_rate': '24000/1001',
                    'avg_frame_rate': '24000/1001',
                },
                {
                    'index': 1,
                    'codec_name': 'aac',
                    'codec_type': 'audio',
                    'sample_rate': '48000',
                    'channels': 6,
                },
            ],
            'format': {
                'filename': '/tmp/movie.mkv',
                'format_name': 'matroska,webm',
                'duration': '3486.590000',
                'size': '2743430123',
                'bit_rate': '6294815',
            },
            'keyframes': [
                '0.000000',
                '6.715000',
                '10.761000',
                '14.473000',
                '24.900000',
                '25.984000',
                '27.819000',
                '30.489000',
                '31.865000',
                '33.200000',
                '36.787000',
                '38.455000',
                '41.208000',
                '44.002000',
                '46.505000',
                '48.757000',
                '50.634000',
                '56.723000',
                '60.352000',
                '62.562000',
                '68.527000',
                '75.909000',
                '86.336000',
                '90.882000',
                '92.384000',
                '96.221000',
            ],
        },
    )

    HlsTranscoder(settings, metadata)


def test_hls_main_playlist_does_not_include_subtitles_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def noop_get_external_subtitles(filename: str) -> list:
        return []

    monkeypatch.setattr(
        'seplis_play.transcoding.hls_transcoder.get_external_subtitles',
        noop_get_external_subtitles,
    )

    settings = TranscodeSettings(
        play_id='a',
        session=uuid4().hex,
        supported_hdr_formats=[],
        supported_video_containers=['mp4'],
        supported_video_codecs=['h264'],
        supported_audio_codecs=['aac'],
        transcode_video_codec='h264',
        transcode_audio_codec='aac',
        format='hls',
    )
    metadata: SourceMetadata = {
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
            },
            {
                'index': 2,
                'codec_name': 'subrip',
                'codec_type': 'subtitle',
                'tags': {'language': 'eng', 'title': 'English'},
                'disposition': {'default': 1},
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

    playlist = asyncio.run(HlsTranscoder(settings, metadata).generate_main_playlist())

    assert 'TYPE=SUBTITLES' not in playlist
    assert 'SUBTITLES="subs"' not in playlist


def test_hls_main_playlist_includes_subtitles_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def noop_get_external_subtitles(filename: str) -> list:
        return []

    monkeypatch.setattr(
        'seplis_play.transcoding.hls_transcoder.get_external_subtitles',
        noop_get_external_subtitles,
    )

    settings = TranscodeSettings(
        play_id='a',
        session=uuid4().hex,
        supported_hdr_formats=[],
        supported_video_containers=['mp4'],
        supported_video_codecs=['h264'],
        supported_audio_codecs=['aac'],
        transcode_video_codec='h264',
        transcode_audio_codec='aac',
        format='hls',
        hls_include_all_subtitles=True,
        hls_subtitle_lang='eng:0',
    )
    metadata: SourceMetadata = {
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
            },
            {
                'index': 2,
                'codec_name': 'subrip',
                'codec_type': 'subtitle',
                'tags': {'language': 'eng', 'title': 'English'},
                'disposition': {'default': 1},
            },
            {
                'index': 3,
                'codec_name': 'subrip',
                'codec_type': 'subtitle',
                'tags': {'language': 'spa', 'title': 'Spanish'},
                'disposition': {'default': 0},
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

    playlist = asyncio.run(HlsTranscoder(settings, metadata).generate_main_playlist())

    assert 'TYPE=SUBTITLES' in playlist
    assert 'SUBTITLES="subs"' in playlist
    assert (
        'LANGUAGE="eng",NAME="English",DEFAULT=YES,AUTOSELECT=YES,FORCED=NO' in playlist
    )
    assert 'LANGUAGE="spa",NAME="Spanish",DEFAULT=NO,AUTOSELECT=NO,FORCED=NO' in playlist
    assert 'FORCED=NO' in playlist
    assert '/hls/subtitle.m3u8?play_id=a&source_index=0&lang=eng%3A0' in playlist
    assert '/hls/subtitle.m3u8?play_id=a&source_index=0&lang=spa%3A1' in playlist
    assert playlist.index('LANGUAGE="eng",NAME="English"') < playlist.index(
        'LANGUAGE="spa",NAME="Spanish"'
    )


def test_hls_main_playlist_only_includes_selected_subtitle_when_not_including_all(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def noop_get_external_subtitles(filename: str) -> list:
        return []

    monkeypatch.setattr(
        'seplis_play.transcoding.hls_transcoder.get_external_subtitles',
        noop_get_external_subtitles,
    )

    settings = TranscodeSettings(
        play_id='a',
        session=uuid4().hex,
        supported_hdr_formats=[],
        supported_video_containers=['mp4'],
        supported_video_codecs=['h264'],
        supported_audio_codecs=['aac'],
        transcode_video_codec='h264',
        transcode_audio_codec='aac',
        format='hls',
        hls_subtitle_lang='eng:0',
    )
    metadata: SourceMetadata = {
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
            },
            {
                'index': 2,
                'codec_name': 'subrip',
                'codec_type': 'subtitle',
                'tags': {'language': 'eng', 'title': 'English'},
                'disposition': {'default': 1},
            },
            {
                'index': 3,
                'codec_name': 'subrip',
                'codec_type': 'subtitle',
                'tags': {'language': 'spa', 'title': 'Spanish'},
                'disposition': {'default': 0},
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

    playlist = asyncio.run(HlsTranscoder(settings, metadata).generate_main_playlist())

    assert (
        'LANGUAGE="eng",NAME="English",DEFAULT=YES,AUTOSELECT=YES,FORCED=NO' in playlist
    )
    assert 'LANGUAGE="spa",NAME="Spanish"' not in playlist
    assert '/hls/subtitle.m3u8?play_id=a&source_index=0&lang=eng%3A0' in playlist
    assert '/hls/subtitle.m3u8?play_id=a&source_index=0&lang=spa%3A1' not in playlist


def test_qsv_tonemap_filter_without_resize_has_valid_scale_expression(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, 'ffmpeg_hwaccel_enabled', True)
    monkeypatch.setattr(config, 'ffmpeg_hwaccel', 'qsv')
    monkeypatch.setattr(config, 'ffmpeg_tonemap_enabled', True)

    settings = TranscodeSettings(
        play_id='a',
        session=uuid4().hex,
        supported_hdr_formats=[],
        supported_video_containers=['mp4'],
        supported_video_codecs=['h264'],
        supported_audio_codecs=['aac'],
        transcode_video_codec='h264',
        transcode_audio_codec='aac',
        supported_video_color_bit_depth=8,
        format='hls',
    )
    metadata: SourceMetadata = {
        'streams': [
            {
                'index': 0,
                'codec_name': 'hevc',
                'profile': 'Main 10',
                'codec_type': 'video',
                'codec_tag_string': '[0][0][0][0]',
                'width': 1920,
                'height': 1080,
                'pix_fmt': 'yuv420p10le',
                'color_transfer': 'smpte2084',
                'color_primaries': 'bt2020',
                'color_space': 'bt2020nc',
                'r_frame_rate': '24000/1001',
            },
            {
                'index': 1,
                'codec_name': 'aac',
                'codec_type': 'audio',
                'sample_rate': '48000',
                'channels': 2,
            },
        ],
        'format': {
            'format_name': 'matroska,webm',
            'filename': '/tmp/movie.mkv',
            'duration': '120.000000',
            'size': '1000000',
            'bit_rate': '2500000',
        },
        'keyframes': ['0.000000', '6.000000'],
    }

    transcoder = HlsTranscoder(settings, metadata)

    vf = transcoder.get_video_filter(width=1920)

    assert vf is not None
    assert 'scale_vaapi=extra_hw_frames=24' in vf
    assert 'scale_vaapi=:extra_hw_frames=24' not in vf


def test_hls_h264_only_does_not_expose_hdr() -> None:
    settings = TranscodeSettings(
        play_id='a',
        session=uuid4().hex,
        supported_hdr_formats=['hdr10'],
        supported_video_containers=['mp4'],
        supported_video_codecs=['h264'],
        supported_audio_codecs=['aac'],
        transcode_video_codec='h264',
        transcode_audio_codec='aac',
        format='hls',
    )
    metadata: SourceMetadata = {
        'streams': [
            {
                'index': 0,
                'codec_name': 'h264',
                'codec_type': 'video',
                'codec_tag_string': 'avc1',
                'width': 1920,
                'height': 1080,
                'pix_fmt': 'yuv420p10le',
                'color_transfer': 'smpte2084',
                'r_frame_rate': '24000/1001',
            },
            {
                'index': 1,
                'codec_name': 'aac',
                'codec_type': 'audio',
                'sample_rate': '48000',
                'channels': 2,
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

    transcoder = HlsTranscoder(settings, metadata)

    assert transcoder.settings.supported_hdr_formats == []
    assert transcoder.can_copy_video is True
    assert transcoder.get_video_range() == 'SDR'
    assert 'VIDEO-RANGE=SDR' in transcoder.get_stream_info_string()


def test_hls_stream_info_uses_shared_output_resolution_and_codecs() -> None:
    settings = TranscodeSettings(
        play_id='a',
        session=uuid4().hex,
        supported_hdr_formats=[],
        supported_video_containers=['mp4'],
        supported_video_codecs=['h264'],
        supported_audio_codecs=['aac'],
        transcode_video_codec='h264',
        transcode_audio_codec='aac',
        max_width=1280,
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

    transcoder = HlsTranscoder(settings, metadata)

    assert transcoder.can_copy_video is False
    assert transcoder.get_output_width() == 1280
    assert transcoder.get_output_resolution() == (1280, 720)
    assert (
        transcoder.get_stream_info_string()
        == 'AVERAGE-BANDWIDTH=5000000,BANDWIDTH=5000000,VIDEO-RANGE=SDR,'
        'CODECS="avc1,mp4a.40.2",RESOLUTION=1280x720,FRAME-RATE=23.976'
    )


def test_hls_h264_source_is_treated_as_sdr_even_if_hevc_is_supported() -> None:
    settings = TranscodeSettings(
        play_id='a',
        session=uuid4().hex,
        supported_hdr_formats=['hdr10'],
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
                'codec_name': 'h264',
                'codec_type': 'video',
                'codec_tag_string': 'avc1',
                'width': 1920,
                'height': 1080,
                'pix_fmt': 'yuv420p10le',
                'color_transfer': 'smpte2084',
                'r_frame_rate': '24000/1001',
            },
            {
                'index': 1,
                'codec_name': 'aac',
                'codec_type': 'audio',
                'sample_rate': '48000',
                'channels': 2,
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

    transcoder = HlsTranscoder(settings, metadata)

    assert transcoder.settings.supported_hdr_formats == []
    assert transcoder.can_copy_video is True
    assert transcoder.get_video_range() == 'SDR'
    assert 'VIDEO-RANGE=SDR' in transcoder.get_stream_info_string()


def test_hls_hevc_hdr10_stream_info_uses_main10_tier_and_pq() -> None:
    settings = TranscodeSettings(
        play_id='a',
        session=uuid4().hex,
        supported_hdr_formats=['hdr10'],
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
                'level': 150,
                'tier': 'High',
                'codec_type': 'video',
                'codec_tag_string': 'hvc1',
                'width': 3840,
                'height': 2160,
                'pix_fmt': 'yuv420p10le',
                'color_transfer': 'smpte2084',
                'color_primaries': 'bt2020',
                'r_frame_rate': '24000/1001',
            },
            {
                'index': 1,
                'codec_name': 'aac',
                'codec_type': 'audio',
                'sample_rate': '48000',
                'channels': 2,
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

    transcoder = HlsTranscoder(settings, metadata)

    assert transcoder.settings.supported_hdr_formats == ['hdr10']
    assert transcoder.can_copy_video is True
    assert transcoder.get_video_range() == 'PQ'
    assert (
        transcoder.get_stream_info_string()
        == 'AVERAGE-BANDWIDTH=2500000,BANDWIDTH=2500000,VIDEO-RANGE=PQ,'
        'CODECS="hvc1.2.4.H150.B0,mp4a.40.2",RESOLUTION=3840x2160,'
        'FRAME-RATE=23.976'
    )


def test_hls_hevc_stream_info_infers_high_tier_from_bitrate() -> None:
    settings = TranscodeSettings(
        play_id='a',
        session=uuid4().hex,
        supported_hdr_formats=['hdr10'],
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
                'level': 150,
                'codec_type': 'video',
                'codec_tag_string': 'hvc1',
                'width': 3840,
                'height': 2160,
                'pix_fmt': 'yuv420p10le',
                'color_transfer': 'smpte2084',
                'color_primaries': 'bt2020',
                'r_frame_rate': '24000/1001',
            },
            {
                'index': 1,
                'codec_name': 'aac',
                'codec_type': 'audio',
                'sample_rate': '48000',
                'channels': 2,
            },
        ],
        'format': {
            'format_name': 'mp4',
            'filename': '/tmp/movie.mp4',
            'duration': '120.000000',
            'size': '1000000',
            'bit_rate': '50000000',
        },
        'keyframes': ['0.000000', '6.000000'],
    }

    transcoder = HlsTranscoder(settings, metadata)

    assert 'CODECS="hvc1.2.4.H150.B0,mp4a.40.2"' in (
        transcoder.get_stream_info_string()
    )


def test_hls_hevc_hdr10_transcode_uses_jellyfin_compatible_sdr_main_profile() -> None:
    settings = TranscodeSettings(
        play_id='a',
        session=uuid4().hex,
        supported_hdr_formats=['hdr10'],
        supported_video_containers=['mp4'],
        supported_video_codecs=['h264', 'hevc'],
        supported_audio_codecs=['aac'],
        transcode_video_codec='hevc',
        transcode_audio_codec='aac',
        max_video_bitrate=10_000_000,
        format='hls',
    )
    metadata: SourceMetadata = {
        'streams': [
            {
                'index': 0,
                'codec_name': 'hevc',
                'profile': 'Main 10',
                'level': 150,
                'tier': 'High',
                'codec_type': 'video',
                'codec_tag_string': 'hvc1',
                'width': 3840,
                'height': 2160,
                'pix_fmt': 'yuv420p10le',
                'color_transfer': 'smpte2084',
                'color_primaries': 'bt2020',
                'r_frame_rate': '24000/1001',
            },
            {
                'index': 1,
                'codec_name': 'aac',
                'codec_type': 'audio',
                'sample_rate': '48000',
                'channels': 2,
            },
        ],
        'format': {
            'format_name': 'mp4',
            'filename': '/tmp/movie.mp4',
            'duration': '120.000000',
            'size': '1000000',
            'bit_rate': '50000000',
        },
        'keyframes': ['0.000000', '6.000000'],
    }

    transcoder = HlsTranscoder(settings, metadata)

    assert transcoder.can_copy_video is False
    assert transcoder.video_output_codec == 'hevc'
    assert transcoder.transcode_decision.video.target_codec == 'hevc'
    assert transcoder.settings.supported_hdr_formats == []
    assert transcoder.settings.supported_video_color_bit_depth == 8
    assert transcoder.get_video_range() == 'SDR'
    assert (
        transcoder.get_stream_info_string()
        == 'AVERAGE-BANDWIDTH=10000000,BANDWIDTH=10000000,VIDEO-RANGE=SDR,'
        'CODECS="hvc1.1.4.L150.B0,mp4a.40.2",RESOLUTION=3840x2160,'
        'FRAME-RATE=23.976'
    )


if __name__ == '__main__':
    run_file(__file__)
