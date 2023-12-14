import asyncio, os
import math
import re
from urllib.parse import urlencode
from decimal import Decimal
from aiofile import async_open
import anyio

from seplis_play_server import logger
from . import video

class Hls_transcoder(video.Transcoder):

    media_name: str = 'media.m3u8'

    def __init__(self, settings: video.Transcode_settings, metadata: dict):
        #if settings.transcode_video_codec not in ('h264', 'hevc'):
        settings.transcode_video_codec = 'h264'
        # Still issues with hevc
        settings.supported_video_codecs = ['h264',]
        super().__init__(settings, metadata)
    
    def ffmpeg_extend_args(self) -> None:
        self.ffmpeg_args.extend([
            *self.keyframe_params(),
            {'-f': 'hls'},
            {'-hls_playlist_type': 'event'},
            {'-hls_segment_type': 'fmp4'},
            {'-hls_time': str(self.segment_time())},
            {'-hls_list_size': '0'},
            {'-start_number': str(self.settings.start_segment or 0)},
            {'-y': None},
        ])

        if self.can_copy_video:
            if self.output_codec == 'h264':
                self.ffmpeg_args.append({'-bsf:v': 'h264_mp4toannexb'})
            elif self.output_codec == 'hevc':
                self.ffmpeg_args.append({'-bsf:v': 'hevc_mp4toannexb'})

        self.ffmpeg_args.append({self.media_path: None})

    @property
    def media_path(self) -> str:
        return os.path.join(self.transcode_folder, self.media_name)

    async def wait_for_media(self):
        await self.wait_for_segment(
            self.transcode_folder, 
            self.settings.start_segment or 0,
        )

    @classmethod
    async def wait_for_segment(cls, transcode_folder: str, segment: str | int):
        async def wait_for():
            while True:
                if await cls.is_segment_ready(transcode_folder, segment):
                    return True
                await asyncio.sleep(0.1)
        try:
            return await asyncio.wait_for(wait_for(), timeout=10)
        except asyncio.TimeoutError:
            logger.error(f'[{transcode_folder}] Timeout waiting for segment {segment}')
            return False

    @classmethod
    async def first_last_transcoded_segment(cls, transcode_folder: str):
        f = os.path.join(transcode_folder, cls.media_name)
        first, last = (-1, -1)
        if await anyio.to_thread.run_sync(os.path.exists, f):
            async with async_open(f, "r") as afp:
                async for line in afp:
                    if not '#' in line:
                        m = re.search(r'(\d+)\.m4s', line)
                        if m:
                            last = int(m.group(1))
                            if first < 0:
                                first = last
        else:
            logger.debug(f'No media file {f}')
        return (first, last)
    
    @classmethod
    async def is_segment_ready(cls, transcode_folder: str, segment: int):
        first_segment, last_segment = await cls.first_last_transcoded_segment(transcode_folder)
        return segment >= first_segment and segment <= last_segment
    
    @staticmethod
    def get_segment_path(transcode_folder: str, segment: int):
        return os.path.join(transcode_folder, f'media{segment}.m4s')

    def generate_hls_playlist(self):
        settings_dict = self.settings.to_args_dict()
        url_settings = urlencode(settings_dict)
        segments = self.get_segments()
        l = []
        l.append('#EXTM3U')
        l.append('#EXT-X-VERSION:7')
        l.append('#EXT-X-PLAYLIST-TYPE:VOD')
        l.append(f'#EXT-X-TARGETDURATION:{round(max(segments)) if len(segments) > 0 else str(self.segment_time())}')
        l.append('#EXT-X-MEDIA-SEQUENCE:0')
        l.append(f'#EXT-X-MAP:URI="/hls/init.mp4?{url_settings}"')

        for i, segment_time in enumerate(segments):
            l.append(f'#EXTINF:{str(segment_time)},')
            l.append(f'/hls/media{i}.m4s?{url_settings}')
        l.append('#EXT-X-ENDLIST')
        return '\n'.join(l)
    
    def get_segments(self):
        if self.can_copy_video:
            return self.calculate_keyframe_segments()
        else:
            return self.calculate_equal_segments()

    def calculate_keyframe_segments(self):
        result: list[Decimal] = []
        target_duration = Decimal(self.segment_time())
        keyframes = [Decimal(t) for t in self.metadata['keyframes']]
        break_time = target_duration
        prev_keyframe = Decimal(0)
        for keyframe in keyframes:
            if keyframe >= break_time:
                result.append(keyframe - prev_keyframe)
                prev_keyframe = keyframe
                break_time += target_duration
        result.append(Decimal(self.metadata['format']['duration']) - prev_keyframe)
        return result

    def calculate_equal_segments(self):
        target_duration = Decimal(self.segment_time())
        duration = Decimal(self.metadata['format']['duration'])
        segments = duration / target_duration
        left_over = duration % target_duration
        result = [target_duration for _ in range(int(segments))]
        if left_over:
            result.append(left_over)
        return result
    
    def start_time_from_segment(self, segment: int) -> Decimal:
        segments = self.get_segments()
        if segment >= len(segments) or segment < 1:
            return Decimal(0)
        return sum(segments[:segment])
    
    def start_segment_from_start_time(self, start_time: Decimal) -> int:
        if start_time <= 0:
            return 0
        segments = self.get_segments()
        time = Decimal(0)
        for i, t in enumerate(segments):
            time += t
            if time > start_time:
                return i
        return 0
        
    def keyframe_params(self) -> list[dict]:
        if self.output_codec_lib == 'copy':
            return []
        args = []
        go_args = []
        keyframe_args = [
            {'-force_key_frames:0': f'expr:gte(t,n_forced*{self.segment_time()})'},
        ]
        if self.video_stream.get('r_frame_rate'):
            r_frame_rate = self.video_stream['r_frame_rate'].split('/')
            r_frame_rate = Decimal(r_frame_rate[0]) / Decimal(r_frame_rate[1])

            v = math.ceil(Decimal(self.segment_time()) * r_frame_rate)
            go_args.extend([
                {'-g:v:0': str(v)},
                {'-keyint_min:v:0': str(v)},
            ])

        # Jellyfin: Unable to force key frames using these encoders, set key frames by GOP.
        if self.output_codec_lib in (
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
        elif self.output_codec_lib in (
            'libx264',
            'libx265',
            'h264_vaapi',
            'hevc_vaapi',
            'av1_vaapi',
        ):
            args.extend(keyframe_args)
            # Jellyfin: Prevent the libx264 from post processing to break the set keyframe.
            if self.output_codec_lib == 'libx264':
                args.append({'-sc_threshold:v:0': '0'})
        else:
            args.extend(keyframe_args + go_args)
        
        # Jellyfin: Global_header produced by AMD HEVC VA-API encoder causes non-playable fMP4 on iOS
        if self.output_codec_lib == 'hevc_vaapi':
            args.extend([
                {'--flags:v': None},
                {'-global_header': None},
            ])

        return args