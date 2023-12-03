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


