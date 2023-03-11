import asyncio
import os
import subprocess
from typing import Union

from seplis_play_server import config, logger

from . import video

class Pipe_transcoder(video.Transcoder):
    
    def ffmpeg_extend_args(self) -> None:
        self.ffmpeg_args.extend([
            {'-f': 'matroska'},
            {'-': None},
        ])

    @property
    def media_path(self) -> str:
        return None

    @property
    def media_name(self) -> str:
        return None

    async def wait_for_media(self) -> bool:
        return None

    async def start(self, send_data_callback) -> Union[bool, bytes]:     
        self.set_ffmpeg_args()        
        args = self.to_subprocess_arguments()   
        logger.debug(f'FFmpeg start args: {" ".join(args)}')
        self.process = await asyncio.create_subprocess_exec(
            os.path.join(config.ffmpeg_folder, 'ffmpeg'),
            *args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.subprocess_env(),
        )
        self.register_session()
        while True:
            data = await asyncio.wait_for(self.process.stdout.read(8192), 10)
            if not data:
                return
            try:
                yield data
            except:
                self.process.terminate()
                return

    def close(self) -> None:
        try:
            self.process.kill()
        except:
            pass