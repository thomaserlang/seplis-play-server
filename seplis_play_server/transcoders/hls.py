import asyncio, os
from aiofile import async_open

from seplis_play_server import logger
from . import video

class Hls_transcoder(video.Transcoder):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # For now force h264 for hls hevc breaks in safari for some reason
        self.settings.transcode_video_codec = 'h264'
        self.settings.supported_video_codecs = ['h264']
    
    def ffmpeg_extend_args(self) -> None:
        self.ffmpeg_args.extend([
            *self.keyframe_params(),
            {'-f': 'hls'},
            {'-hls_playlist_type': 'event'},
            {'-hls_segment_type': 'fmp4'},
            {'-hls_time': str(self.segment_time())},
            {'-hls_list_size': '0'},
            {self.media_path: None},
        ])

    @property
    def media_path(self) -> str:
        return os.path.join(self.transcode_folder, self.media_name)

    @property
    def media_name(self) -> str:
        return 'media.m3u8'

    async def wait_for_media(self):
        files = 0

        while True:
            if os.path.exists(self.media_path):
                async with async_open(self.media_path, "r") as afp:
                    async for line in afp:
                        if not '#' in line:
                            files += 1   
            if files >= 1:
                return True
            await asyncio.sleep(0.5)

    async def write_hls_playlist(self) -> None:
        l = []
        l.append('#EXTM3U')
        l.append('#EXT-X-VERSION:7')
        l.append('#EXT-X-PLAYLIST-TYPE:VOD')
        l.append(f'#EXT-X-TARGETDURATION:{str(self.segment_time())}')
        l.append('#EXT-X-MEDIA-SEQUENCE:0')

        # Keyframes is in self.metadata['keyframes']
        
        # Make the EXTINF lines
        prev = 0.0
        for i, t in enumerate(self.metadata['keyframes']):
            l.append(f'#EXTINF:{str(t-prev)},')
            l.append(f'media{i}.m4s')

        logger.info(l)

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
            r_frame_rate = int(r_frame_rate[0]) / int(r_frame_rate[1])

            v = self.segment_time() * r_frame_rate
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