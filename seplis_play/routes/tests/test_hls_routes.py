import asyncio
from typing import Any, cast

import pytest

from seplis_play import config
from seplis_play.routes import hls_routes
from seplis_play.transcoding.base_transcoder import (
    close_session,
    refresh_session_timeout,
    sessions,
)
from seplis_play.transcoding.hls_transcoder import HlsTranscoder
from seplis_play.transcoding.transcode_settings_schema import TranscodeSettings


def make_settings(session: str) -> TranscodeSettings:
    return TranscodeSettings(
        play_id='play-id',
        session=session,
        supported_hdr_formats=[],
        supported_audio_codecs=['aac'],
        supported_video_containers=['mp4'],
        supported_video_codecs=['h264'],
    )


@pytest.mark.asyncio
async def test_transcode_starts_are_serialized_per_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active = 0
    peak_active = 0

    async def fake_start(
        settings: TranscodeSettings,
        start_segment: int,
    ) -> Any:
        nonlocal active, peak_active
        active += 1
        peak_active = max(peak_active, active)
        await asyncio.sleep(0.01)
        active -= 1
        return (settings, start_segment)

    monkeypatch.setattr(hls_routes, '_start_transcode', fake_start)
    settings = make_settings('a' * 32)

    await asyncio.gather(
        hls_routes.start_transcode(settings, 10),
        hls_routes.start_transcode(settings, 11),
    )

    assert peak_active == 1


@pytest.mark.asyncio
async def test_pause_thresholds_are_measured_in_seconds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Runner:
        paused = False

        def pause(self) -> None:
            self.paused = True

        def resume(self) -> None:
            self.paused = False

    last_segment = 100

    async def first_last(_folder: str) -> tuple[int, int]:
        return (0, last_segment)

    runner = Runner()
    session = 'b' * 32
    sessions[session] = cast(
        Any,
        type('Session', (), {'segment_time': 3, 'ffmpeg_runner': runner})(),
    )
    monkeypatch.setattr(HlsTranscoder, 'first_last_transcoded_segment', first_last)
    monkeypatch.setattr(config, 'ffmpeg_pause_threshold_seconds', 300)
    monkeypatch.setattr(config, 'ffmpeg_resume_threshold_seconds', 150)

    try:
        await hls_routes.manage_transcoder_pause(session, '/tmp/transcode', 0)
        assert runner.paused is True

        last_segment = 40
        await hls_routes.manage_transcoder_pause(session, '/tmp/transcode', 0)
        assert runner.paused is False
    finally:
        sessions.pop(session, None)


@pytest.mark.asyncio
async def test_stale_timeout_does_not_close_replacement_session() -> None:
    old_runner = object()
    current_runner = object()
    session = 'c' * 32
    sessions[session] = cast(
        Any,
        type('Session', (), {'ffmpeg_runner': current_runner})(),
    )

    try:
        await close_session(session, expected_runner=cast(Any, old_runner))

        assert sessions[session].ffmpeg_runner is current_runner
    finally:
        sessions.pop(session, None)


@pytest.mark.asyncio
async def test_stale_timeout_does_not_close_refreshed_session() -> None:
    runner = object()
    session = 'd' * 32
    sessions[session] = cast(
        Any,
        type(
            'Session',
            (),
            {
                'ffmpeg_runner': runner,
                'timeout_generation': 2,
            },
        )(),
    )

    try:
        await close_session(
            session,
            expected_runner=cast(Any, runner),
            expected_timeout_generation=1,
        )

        assert sessions[session].ffmpeg_runner is runner
    finally:
        sessions.pop(session, None)


@pytest.mark.asyncio
async def test_refresh_session_timeout_replaces_timer() -> None:
    loop = asyncio.get_running_loop()
    old_timer = loop.call_later(3600, lambda: None)
    runner = object()
    session = 'e' * 32
    sessions[session] = cast(
        Any,
        type(
            'Session',
            (),
            {
                'ffmpeg_runner': runner,
                'call_later': old_timer,
                'timeout_generation': 1,
            },
        )(),
    )

    try:
        assert await refresh_session_timeout(session) is True
        assert old_timer.cancelled()
        assert sessions[session].timeout_generation == 2
        assert sessions[session].call_later is not old_timer
    finally:
        call_later = sessions[session].call_later
        if call_later is not None:
            call_later.cancel()
        sessions.pop(session, None)
