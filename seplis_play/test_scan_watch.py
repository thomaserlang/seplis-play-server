import asyncio
from pathlib import Path
from unittest import mock

import pytest
from watchfiles import Change

from seplis_play.config import ConfigPlayScanModel
from seplis_play.scan_watch import worker


@pytest.mark.asyncio
async def test_worker_ignores_hidden_subtitle() -> None:
    queue: asyncio.Queue[tuple[Change, str, ConfigPlayScanModel] | None] = asyncio.Queue()
    scan = ConfigPlayScanModel(type='series', path=Path('/series'))
    task = asyncio.create_task(worker(queue))

    with mock.patch('seplis_play.scan_watch.get_scanner') as get_scanner:
        await queue.put((Change.added, '/series/.bazarr-sync-temp.srt', scan))
        await asyncio.wait_for(queue.join(), timeout=1)
        get_scanner.assert_not_called()

    await queue.put(None)
    await task
