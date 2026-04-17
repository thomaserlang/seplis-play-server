"""
FFmpeg process execution with progress tracking and stall detection.

Handles spawning FFmpeg processes, reading stdout/stderr, parsing progress,
and detecting stalls with graceful termination.
"""

import asyncio
import re
import shlex
import signal
import time
from collections.abc import Callable
from decimal import Decimal

from loguru import logger

from .ffmpeg_schemas import MediaInfo, TranscodeProgress


class ProgressParser:
    """
    Centralized FFmpeg progress parsing with throttling.

    Moves regex parsing out of the hot stderr loop and provides
    throttled updates to avoid overwhelming callbacks.
    """

    _RE_FRAME = re.compile(r'frame=\s*(\d+)')
    _RE_FPS = re.compile(r'fps=\s*([\d.]+|N/A)')
    _RE_BITRATE = re.compile(r'bitrate=\s*([\d.]+\s*[kMG]?bits/s|N/A)')
    _RE_SIZE = re.compile(r'size=\s*(\d+)\s*(kB|MB|B)?')
    _RE_TIME_FULL = re.compile(r'time=\s*(\d+):(\d+):(\d+\.?\d*)')
    _RE_TIME_SHORT = re.compile(r'time=\s*(\d+):(\d+\.?\d*)')
    _RE_SPEED = re.compile(r'speed=\s*([\d.]+)x')
    _RE_QUALITY = re.compile(r'q=\s*([\d.-]+)')

    def __init__(self, throttle_interval: float = 0.5) -> None:
        self.throttle_interval = throttle_interval
        self._last_callback_time = 0.0
        self._pending_line: str | None = None

    def should_parse(self, line: str) -> bool:
        """Check if line contains progress info worth parsing."""
        return 'frame=' in line or 'size=' in line or 'time=' in line

    def parse(
        self, line: str, progress: TranscodeProgress, media_info: MediaInfo
    ) -> bool:
        """
        Parse FFmpeg progress line and update progress object.

        Returns True if parsing found progress data.
        """
        found_progress = False

        match = self._RE_FRAME.search(line)
        if match:
            try:
                progress.frame = int(match.group(1))
                found_progress = True
            except ValueError, TypeError:
                pass

        match = self._RE_FPS.search(line)
        if match and match.group(1) != 'N/A':
            try:
                progress.fps = Decimal(match.group(1))
            except ValueError, TypeError:
                pass

        match = self._RE_BITRATE.search(line)
        if match and match.group(1) != 'N/A':
            progress.bitrate = match.group(1).strip()

        match = self._RE_SIZE.search(line)
        if match:
            try:
                size_val = int(match.group(1))
                unit = match.group(2) or 'kB'
                if unit == 'MB':
                    progress.total_size = size_val * 1024 * 1024
                elif unit == 'kB':
                    progress.total_size = size_val * 1024
                else:
                    progress.total_size = size_val
                found_progress = True
            except ValueError, TypeError:
                pass

        match = self._RE_TIME_FULL.search(line)
        if match:
            try:
                h, m, s = match.groups()
                progress.time = int(h) * 3600 + int(m) * 60 + Decimal(s)
                found_progress = True
            except ValueError, TypeError:
                pass
        else:
            match = self._RE_TIME_SHORT.search(line)
            if match:
                try:
                    m, s = match.groups()
                    progress.time = int(m) * 60 + Decimal(s)
                    found_progress = True
                except ValueError, TypeError:
                    pass

        match = self._RE_SPEED.search(line)
        if match:
            try:
                progress.speed = float(match.group(1))
            except ValueError, TypeError:
                pass

        if media_info.duration > 0 and progress.time > 0:
            progress.percent = min(
                Decimal('99.9'), (progress.time / media_info.duration) * 100
            )

        return found_progress

    def should_callback(self) -> bool:
        """Check if enough time has passed to fire callback (throttling)."""
        now = time.time()
        if now - self._last_callback_time >= self.throttle_interval:
            self._last_callback_time = now
            return True
        return False


class FFmpegRunner:
    """
    Executes FFmpeg processes with progress tracking and stall detection.

    Features:
    - Async stdout/stderr reading to prevent pipe blocking
    - Progress parsing with throttled callbacks
    - Stall detection with grace period and file growth checks
    - Graceful process termination with platform-specific signals
    """

    def __init__(self) -> None:
        self._cancelled = asyncio.Event()
        self._startup_event = asyncio.Event()
        self._tasks: list[asyncio.Task] = []
        self._stderr: list[str] = []
        self.process: asyncio.subprocess.Process | None = None
        self.cmd: list[str] = []
        self.paused = False

    def pause(self) -> None:
        if self.process is None or self.process.returncode is not None or self.paused:
            return
        try:
            self.process.send_signal(signal.SIGSTOP)
            self.paused = True
            logger.debug('[FFmpeg] Paused (SIGSTOP)')
        except ProcessLookupError, OSError:
            pass

    def resume(self) -> None:
        if self.process is None or self.process.returncode is not None or not self.paused:
            return
        try:
            self.process.send_signal(signal.SIGCONT)
            self.paused = False
            logger.debug('[FFmpeg] Resumed (SIGCONT)')
        except ProcessLookupError, OSError:
            pass

    async def cancel(self) -> None:
        if self.process is None:
            return
        self.resume()  # Wake up if paused so SIGINT is handled promptly
        await self._graceful_terminate(self.process)
        await self._cancelled.wait()

    async def start(
        self,
        cmd: list[str],
        media_info: MediaInfo,
        progress_callback: Callable[[TranscodeProgress], None] | None = None,
    ) -> asyncio.subprocess.Process | None:
        log_prefix = '[FFmpeg]'
        logger.info(f'{log_prefix} Running: {shlex.join(cmd)}')
        self.cmd = cmd

        self.process = await self._spawn_process(cmd, log_prefix)
        if self.process is None:
            raise RuntimeError(f'{log_prefix} Failed to start FFmpeg process')

        progress = TranscodeProgress()
        progress_parser = ProgressParser(throttle_interval=0.5)

        self._tasks.extend(
            [
                asyncio.create_task(
                    self._read_stderr(
                        self.process,
                        media_info,
                        progress,
                        progress_parser,
                        progress_callback,
                        log_prefix,
                    )
                ),
            ]
        )

        try:
            await asyncio.wait_for(self._startup_event.wait(), timeout=120.0)
            if self._cancelled.is_set():
                raise TimeoutError()
            return self.process
        except TimeoutError as e:
            raise RuntimeError(
                f'{log_prefix} FFmpeg did not produce progress output  '
                f'\n{"".join(self._stderr)}'
                f'\nCommand: {shlex.join(cmd)}'
            ) from e

    async def _spawn_process(
        self, cmd: list[str], log_prefix: str
    ) -> asyncio.subprocess.Process | None:
        try:
            return await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
        except Exception as e:
            logger.error(
                f'{log_prefix} Failed to start FFmpeg: {e}\nCommand: {shlex.join(cmd)}'
            )
            return None

    async def _read_stderr(
        self,
        process: asyncio.subprocess.Process,
        media_info: MediaInfo,
        progress: TranscodeProgress,
        parser: ProgressParser,
        progress_callback: Callable[[TranscodeProgress], None] | None,
        log_prefix: str,
    ) -> None:
        try:
            while True:
                if process.stderr is None:
                    break

                line = await process.stderr.readline()
                if not line:
                    break

                line_str = line.decode('utf-8', errors='ignore')
                self._stderr.append(line_str)
                if len(self._stderr) > 30:
                    self._stderr.pop(0)

                if parser.should_parse(line_str):
                    if parser.parse(line_str, progress, media_info):
                        if progress.frame > 0:
                            self._startup_event.set()

                    if progress_callback and parser.should_callback():
                        try:
                            progress_callback(progress)
                        except Exception as e:
                            logger.warning(f'{log_prefix} Progress callback error: {e}')
        except Exception as e:
            logger.error(f'{log_prefix} stderr reader error: {e}')
        finally:
            await asyncio.wait_for(process.wait(), timeout=5.0)
            if process.returncode and process.returncode > 0:
                logger.error(
                    f'{log_prefix} FFmpeg exited with code {process.returncode}. '
                    f'\n{"".join(self._stderr)}'
                    f'\nCommand: {shlex.join(self.cmd)}'
                )
                await self._graceful_terminate(process)
            self._startup_event.set()

    async def _graceful_terminate(self, process: asyncio.subprocess.Process) -> None:
        try:
            if process.returncode is not None:
                return
            try:
                process.send_signal(signal.SIGINT)
            except ProcessLookupError, OSError:
                pass

            try:
                await asyncio.wait_for(process.wait(), timeout=5.0)
                logger.debug('[FFmpeg] Terminated gracefully')
                return
            except TimeoutError:
                pass

            try:
                process.terminate()
                await asyncio.wait_for(process.wait(), timeout=3.0)
                logger.debug('[FFmpeg] Terminated with SIGTERM')
                return
            except TimeoutError, ProcessLookupError, OSError:
                pass

            try:
                process.kill()
                await process.wait()
                logger.warning('[FFmpeg] Killed forcefully')
            except ProcessLookupError, OSError:
                pass

        except Exception as e:
            logger.warning(f'[FFmpeg] Error during termination: {e}')
        finally:
            for task in self._tasks:
                if not task.done():
                    task.cancel()
            self._cancelled.set()
            self._startup_event.set()
