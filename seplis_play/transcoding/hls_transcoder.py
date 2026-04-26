import asyncio
import math
import os
import re
from decimal import Decimal
from urllib.parse import urlencode

import iso639
from aiofile import AIOFile, LineReader

from seplis_play import logger
from seplis_play.scanners.subtitles.subtitles import get_external_subtitles
from seplis_play.schemas.source_metadata_schemas import (
    SourceMetadata,
)
from seplis_play.schemas.source_schemas import SourceStream
from seplis_play.transcoding.tests.test_transcode_schema import TranscodeSettings

from . import base_transcoder


class HlsTranscoder(base_transcoder.BaseTranscoder):
    MEDIA_NAME: str = 'media.m3u8'
    CODECES = ('h264', 'hevc', 'av1')
    HDR_CODECS = ('hevc', 'av1')
    HEVC_MAIN_TIER_MAX_BITRATES = {
        120: 12_000_000,
        123: 20_000_000,
        150: 25_000_000,
        153: 40_000_000,
        156: 60_000_000,
        180: 60_000_000,
        183: 120_000_000,
        186: 240_000_000,
    }

    def __init__(self, settings: TranscodeSettings, metadata: SourceMetadata) -> None:
        if settings.transcode_video_codec not in self.CODECES:
            settings.transcode_video_codec = 'h264'
        settings.supported_video_codecs = [
            c for c in settings.supported_video_codecs if c in self.CODECES
        ]  # Filter out unsupported codecs for hls
        source_codec = next(
            (
                stream.get('codec_name')
                for stream in metadata.get('streams', [])
                if stream.get('codec_type') == 'video'
            ),
            None,
        )
        if source_codec not in self.HDR_CODECS or not any(
            codec in self.HDR_CODECS for codec in settings.supported_video_codecs
        ):
            settings.supported_hdr_formats = []
        super().__init__(settings, metadata)

    def ffmpeg_extend_args(self) -> None:
        self.ffmpeg_args.extend(
            [
                *self.keyframe_params(),
                {'-f': 'hls'},
                {'-hls_playlist_type': 'event'},
                {'-hls_segment_type': 'fmp4'},
                {'-hls_time': str(self.segment_time())},
                {'-hls_list_size': '0'},
                {'-hls_segment_options': 'movflags=+frag_discont'},
                {'-start_number': str(self.settings.start_segment or 0)},
                {'-y': None},
            ]
        )

        if self.can_copy_video:
            if self.video_output_codec == 'h264':
                self.ffmpeg_args.append({'-bsf:v': 'h264_mp4toannexb'})
            elif self.video_output_codec == 'hevc':
                self.ffmpeg_args.append({'-bsf:v': 'hevc_mp4toannexb'})

        self.ffmpeg_args.append({self.media_path: None})

    @property
    def media_path(self) -> str:
        return os.path.join(self.transcode_folder, self.MEDIA_NAME)

    @classmethod
    async def wait_for_segment(cls, transcode_folder: str, segment: str | int) -> bool:
        async def wait_for() -> bool:
            while True:
                if await cls.is_segment_ready(transcode_folder, segment):
                    return True
                await asyncio.sleep(0.1)

        try:
            return await asyncio.wait_for(wait_for(), timeout=10)
        except TimeoutError:
            logger.error(f'[{transcode_folder}] Timeout waiting for segment {segment}')
            return False

    @classmethod
    async def first_last_transcoded_segment(
        cls, transcode_folder: str
    ) -> tuple[int, int]:
        f = os.path.join(transcode_folder, cls.MEDIA_NAME)
        first, last = (-1, -1)
        if os.path.exists(f):
            async with AIOFile(f, 'r') as afp:
                async for line in LineReader(afp):
                    if not isinstance(line, str):
                        line = bytes(line).decode()
                    if '#' not in line:
                        m = re.search(r'(\d+)\.m4s', line)
                        if m:
                            last = int(m.group(1))
                            if first < 0:
                                first = last
        else:
            logger.debug(f'No media file {f}')
        return (first, last)

    @classmethod
    async def is_segment_ready(cls, transcode_folder: str, segment: str | int) -> bool:
        first_segment, last_segment = await cls.first_last_transcoded_segment(
            transcode_folder
        )
        return int(segment) >= first_segment and int(segment) <= last_segment

    @staticmethod
    def get_segment_path(transcode_folder: str, segment: int) -> str:
        return os.path.join(transcode_folder, f'media{segment}.m4s')

    def generate_media_playlist(self) -> str:
        settings_dict = self.settings.to_args_dict()
        settings_dict.pop('start_segment', None)
        settings_dict.pop('start_time', None)
        url_settings = urlencode(settings_dict)
        segments = self.get_segments()
        playlist = []
        playlist.append('#EXTM3U')
        playlist.append('#EXT-X-VERSION:7')
        playlist.append('#EXT-X-PLAYLIST-TYPE:VOD')
        playlist.append(
            f'#EXT-X-TARGETDURATION:'
            f'{round(max(segments)) if len(segments) > 0 else str(self.segment_time())}'
        )
        playlist.append('#EXT-X-MEDIA-SEQUENCE:0')
        playlist.append(f'#EXT-X-MAP:URI="/hls/init.mp4?{url_settings}"')

        for i, segment_time in enumerate(segments):
            playlist.append(f'#EXTINF:{str(segment_time)},')
            playlist.append(f'/hls/media{i}.m4s?{url_settings}')
        playlist.append('#EXT-X-ENDLIST')
        return '\n'.join(playlist)

    async def get_subtitle_streams(self) -> list[SourceStream]:
        result: list[SourceStream] = self.source.subtitles.copy()
        external_subs = await get_external_subtitles(self.metadata['format']['filename'])
        result.extend(external_subs)
        if (
            not self.settings.hls_include_all_subtitles
            and self.settings.hls_subtitle_lang
        ):
            selected = base_transcoder.stream_by_lang(
                result, self.settings.hls_subtitle_lang
            )
            if selected is not None:
                result = [stream for stream in result if stream.index == selected.index]
        return result

    async def generate_subtitle_playlist(self) -> list[str]:
        result: list[str] = []
        subtitle_streams: list[SourceStream] = await self.get_subtitle_streams()
        default_subtitle = base_transcoder.stream_by_lang(
            subtitle_streams, self.settings.hls_subtitle_lang
        )
        for stream in subtitle_streams:
            lang_param = f'{stream.language}:{stream.group_index}'
            selected = (
                'YES'
                if default_subtitle is not None and stream.index == default_subtitle.index
                else 'NO'
            )
            subtitle_params: dict[str, str | int | Decimal] = {
                'play_id': self.settings.play_id,
                'source_index': self.settings.source_index,
                'lang': lang_param,
            }
            if self.settings.hls_subtitle_offset:
                subtitle_params['offset'] = self.settings.hls_subtitle_offset
            subtitle_url = f'/hls/subtitle.m3u8?{urlencode(subtitle_params)}'
            language_title = (
                iso639.Lang(stream.language).name
                if iso639.is_language(stream.language or '')
                else stream.language
            )
            result.append(
                f'#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subs",'
                f'LANGUAGE="{stream.language}",NAME="{stream.title or language_title}",'
                f'DEFAULT={selected},AUTOSELECT={selected},FORCED=NO,'
                f'URI="{subtitle_url}"'
            )
        return result

    async def generate_main_playlist(self) -> str:
        settings_dict = self.settings.to_args_dict()
        url_settings = urlencode(settings_dict)

        playlist = ['#EXTM3U']

        subtitle_playlist = []
        if self.settings.hls_include_all_subtitles or self.settings.hls_subtitle_lang:
            subtitle_playlist = await self.generate_subtitle_playlist()
            playlist.extend(subtitle_playlist)

        stream_inf = self.get_stream_info_string()
        if subtitle_playlist:
            stream_inf += ',SUBTITLES="subs"'
        playlist.append(f'#EXT-X-STREAM-INF:{stream_inf}')
        playlist.append(f'/hls/media.m3u8?{url_settings}')
        return '\n'.join(playlist)

    def get_video_range(self) -> str:
        if not self.can_copy_video or self.video_output_codec not in self.HDR_CODECS:
            return 'SDR'
        if self.video_color.range_type == 'hdr10':
            return 'PQ'
        if self.video_color.range_type == 'hlg':
            return 'HLG'
        return 'SDR'

    def get_stream_info_string(self) -> str:
        info = []
        video_bitrate = self.get_video_bitrate()
        info.append(f'AVERAGE-BANDWIDTH={video_bitrate}')
        info.append(f'BANDWIDTH={video_bitrate}')
        info.append(f'VIDEO-RANGE={self.get_video_range()}')
        codecs = self.get_codecs_string()
        if codecs:
            info.append(f'CODECS="{",".join(codecs)}"')
        width, height = self.get_output_resolution()
        info.append(f'RESOLUTION={width}x{height}')
        frame_rate = self.get_frame_rate()
        if frame_rate:
            info.append(f'FRAME-RATE={frame_rate}')
        return ','.join(info)

    def get_frame_rate(self) -> str:
        frame_rate_value = self.video_stream.get('r_frame_rate')
        if not frame_rate_value:
            return ''
        numerator, denominator = frame_rate_value.split('/')
        if denominator == '0':
            return ''
        frame_rate = Decimal(numerator) / Decimal(denominator)
        return f'{frame_rate:.3f}'

    def get_segments(self) -> list[Decimal]:
        if self.can_copy_video:
            return self.calculate_keyframe_segments()
        return self.calculate_equal_segments()

    def calculate_keyframe_segments(self) -> list[Decimal]:
        result: list[Decimal] = []
        target_duration = Decimal(self.segment_time())
        keyframes = [Decimal(t) for t in (self.metadata.get('keyframes') or [])]
        break_time = target_duration
        prev_keyframe = Decimal(0)
        for keyframe in keyframes:
            if keyframe >= break_time:
                result.append(keyframe - prev_keyframe)
                prev_keyframe = keyframe
                break_time += target_duration
        result.append(self.source.duration - prev_keyframe)
        return result

    def calculate_equal_segments(self) -> list[Decimal]:
        target_duration = Decimal(self.segment_time())
        segments = self.source.duration / target_duration
        left_over = self.source.duration % target_duration
        result = [target_duration for _ in range(int(segments))]
        if left_over:
            result.append(left_over)
        return result

    def start_time_from_segment(self, segment: int) -> Decimal:
        segments = self.get_segments()
        r = Decimal(sum(segments[:segment]))
        if self.can_copy_video:
            # It seems that sending ffmpeg the precise start time of
            # the keyframe often results in it starting a few seconds before.
            # Adding 0.5 seconds seems to fix this most of the time,
            # tried with 0.1 and 0.3 which seemed to work less often.
            r += Decimal(0.5)
        return r

    def start_segment_from_start_time(self, start_time: Decimal) -> int:
        if start_time <= 0:
            return 0
        segments = self.get_segments()
        time = Decimal(0)
        for i, t in enumerate(segments):
            time += t
            if time >= start_time:
                return i
        return 0

    def keyframe_params(self) -> list[dict[str, str | None]]:
        if self.video_output_codec_lib == 'copy':
            return []
        args: list[dict[str, str | None]] = []
        go_args: list[dict[str, str | None]] = []
        keyframe_args: list[dict[str, str | None]] = [
            {'-force_key_frames:0': f'expr:gte(t,n_forced*{self.segment_time()})'},
        ]
        r_frame_rate_value = self.video_stream.get('r_frame_rate')
        if r_frame_rate_value:
            r_frame_rate = r_frame_rate_value.split('/')
            r_frame_rate = Decimal(r_frame_rate[0]) / Decimal(r_frame_rate[1])

            v = math.ceil(Decimal(self.segment_time()) * r_frame_rate)
            go_args.extend(
                [
                    {'-g:v:0': str(v)},
                    {'-keyint_min:v:0': str(v)},
                ]
            )

        # Jellyfin: Unable to force key frames using these encoders,
        # set key frames by GOP.
        if self.video_output_codec_lib in (
            'h264_qsv',
            'h264_nvenc',
            'h264_amf',
            'hevc_qsv',
            'hevc_nvenc',
            'av1_qsv',
            'av1_nvenc',
            'av1_amf',
            'libsvtav1',
        ):
            args.extend(go_args)
        elif self.video_output_codec_lib in (
            'libx264',
            'libx265',
            'h264_vaapi',
            'hevc_vaapi',
            'av1_vaapi',
        ):
            args.extend(keyframe_args)
            # Jellyfin: Prevent the libx264 from post processing to break the
            # set keyframe.
            if self.video_output_codec_lib == 'libx264':
                args.append({'-sc_threshold:v:0': '0'})
        else:
            args.extend(keyframe_args + go_args)

        # Jellyfin: Global_header produced by AMD HEVC VA-API encoder
        # causes non-playable fMP4 on iOS
        if self.video_output_codec_lib == 'hevc_vaapi':
            args.extend(
                [
                    {'--flags:v': None},
                    {'-global_header': None},
                ]
            )

        return args

    def get_codecs_string(self) -> list[str]:
        codecs = [
            self.get_video_codec_string(),
            self.get_audio_codec_string(),
        ]
        return [c for c in codecs if c]

    def get_video_codec_string(self) -> str:
        if self.video_output_codec == 'h264':
            if self.can_copy_video:
                return self.get_h264_codec_string(
                    self.video_stream.get('profile', ''),
                    self.video_stream.get('level', 0),
                )
            return 'avc1'
        if self.video_output_codec == 'hevc':
            if self.can_copy_video:
                return self.get_hevc_codec_string(
                    self.video_stream.get('profile', ''),
                    self.video_stream.get('level', 0),
                    self.video_stream.get('tier', ''),
                    self.source.bitrate,
                )
            return 'hvc1'
        if self.video_output_codec == 'av1':
            return 'av01'
        return ''

    def get_audio_codec_string(self) -> str:
        if self.audio_output_codec == 'aac':
            return self.get_aac_codec_string('')
        if self.audio_output_codec == 'ac3':
            return 'mp4a.a5'
        if self.audio_output_codec == 'eac3':
            return 'mp4a.a6'
        if self.audio_output_codec == 'opus':
            return 'Opus'
        if self.audio_output_codec == 'flac':
            return 'fLaC'
        if self.audio_output_codec == 'mp3':
            return 'mp4a.40.34'
        return ''

    def get_h264_codec_string(self, profile: str, level: int) -> str:
        r = 'avc1'
        profile = profile.lower()
        if profile == 'high':
            r += '.6400'
        elif profile == 'main':
            r += '.4D40'
        elif profile == 'baseline':
            r += '.42E0'
        else:
            r += '.4240'
        r += f'{level:02X}'
        return r

    def get_hevc_codec_string(
        self, profile: str, level: int, tier: str = '', bitrate: int = 0
    ) -> str:
        r = 'hvc1'
        normalized_profile = profile.lower().replace(' ', '')
        if 'main10' in normalized_profile:
            r += '.2.4'
        else:
            r += '.1.4'
        tier_prefix = (
            'H' if self.is_hevc_high_tier(profile, level, tier, bitrate) else 'L'
        )
        r += f'.{tier_prefix}{level}.B0'
        return r

    def is_hevc_high_tier(
        self, profile: str, level: int, tier: str = '', bitrate: int = 0
    ) -> bool:
        if tier.lower() == 'high' or 'high' in profile.lower():
            return True
        main_tier_max_bitrate = self.HEVC_MAIN_TIER_MAX_BITRATES.get(level)
        return bool(main_tier_max_bitrate and bitrate > main_tier_max_bitrate)

    def get_aac_codec_string(self, profile: str) -> str:
        r = 'mp4a'
        if profile.lower() == 'he':
            r += '.40.5'
        else:
            r += '.40.2'
        return r
