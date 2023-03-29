import asyncio, os
from aiofile import async_open
from . import video

class Hls_transcoder(video.Transcoder):
    
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