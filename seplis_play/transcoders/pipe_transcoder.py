import asyncio
import os
import subprocess
from collections.abc import AsyncGenerator

from seplis_play import config, logger

from . import base_transcoder


class Pipe_transcoder(base_transcoder.Transcoder):
    def ffmpeg_extend_args(self) -> None:
        self.ffmpeg_args.extend(
            [
                {'-f': 'matroska'},
                {'-': None},
            ]
        )

    @property
    def media_path(self) -> str | None:
        return None

    @property
    def media_name(self) -> str | None:
        return None

    async def wait_for_media(self) -> bool:
        return True

    async def start(self) -> AsyncGenerator[bytes]:
        await self.set_ffmpeg_args()
        args = base_transcoder.to_subprocess_arguments(self.ffmpeg_args)
        logger.debug(f'FFmpeg start args: {" ".join(args)}')
        self.process = await asyncio.create_subprocess_exec(
            os.path.join(config.ffmpeg_folder, 'ffmpeg'),
            *args,
            stdout=subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        asyncio.create_task(
            base_transcoder._log_ffmpeg_stderr(self.settings.session, self.process)
        )
        self.register_session()
        assert self.process.stdout is not None
        while True:
            data = await asyncio.wait_for(self.process.stdout.read(8192), 10)
            if not data:
                return
            try:
                yield data
            except Exception:
                self.process.terminate()
                return

    def close(self) -> None:
        try:
            self.process.kill()
        except Exception:
            pass
