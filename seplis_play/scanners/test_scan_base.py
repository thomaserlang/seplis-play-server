from typing import cast
from unittest import mock

import pytest

from seplis_play.scanners.scan_base import MediaProbeError, PlayScan
from seplis_play.schemas.source_metadata_schemas import SourceMetadata
from seplis_play.schemas.source_schemas import source_streams_from_metadata


@pytest.mark.asyncio
async def test_get_metadata_accepts_probe_stderr_on_success() -> None:
    scanner = PlayScan(scan_path='/')
    process = mock.AsyncMock()
    process.returncode = 0
    process.communicate.return_value = (
        b'{"streams": [{"index": 0, "codec_type": "video"}], '
        b'"format": {"filename": "/episode.mkv"}}',
        b'[h264] number of reference frames exceeds max\n',
    )
    with (
        mock.patch('os.path.exists', return_value=True),
        mock.patch('seplis_play.scanners.scan_base.config.extract_keyframes', False),
        mock.patch('asyncio.create_subprocess_exec', return_value=process),
    ):
        metadata = await scanner.get_metadata('/episode.mkv')

    assert metadata['format']['filename'] == '/episode.mkv'


@pytest.mark.asyncio
async def test_get_metadata_rejects_failed_probe() -> None:
    scanner = PlayScan(scan_path='/')
    process = mock.AsyncMock()
    process.returncode = 1
    process.communicate.return_value = (
        b'',
        b'Invalid data found when processing input\n',
    )
    with (
        mock.patch('os.path.exists', return_value=True),
        mock.patch('asyncio.create_subprocess_exec', return_value=process),
        pytest.raises(MediaProbeError, match='Invalid data found'),
    ):
        await scanner.get_metadata('/broken.mkv')


def test_unknown_subtitle_codec_is_not_offered() -> None:
    metadata = cast(
        SourceMetadata,
        {
            'streams': [
                {
                    'index': 2,
                    'codec_type': 'subtitle',
                    'codec_name': 'none',
                    'tags': {'language': 'eng'},
                }
            ],
            'format': {'filename': '/episode.mkv'},
        },
    )

    assert source_streams_from_metadata(metadata, 'subtitle') == []
