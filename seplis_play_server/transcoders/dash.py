import asyncio, os
from . import video

class Dash_transcoder(video.Transcoder):
    
    def ffmpeg_extend_args(self) -> None:
        self.ffmpeg_args.extend([
            {'-f': 'dash'},
            {'-segment_time': str(self.segment_time())},
            {'-segment_start_number': '0'},
            {'-segment_format_options': 'ignore_readorder=1'},
            {self.media_path: None},
        ])

    @property
    def media_path(self) -> str:
        return os.path.join(self.temp_folder, self.media_name)

    @property
    def media_name(self) -> str:
        return 'media.mpd'

    async def wait_for_media(self):
        while True:
            await asyncio.sleep(0.5)
            if os.path.exists(self.media_path):
                return True
            