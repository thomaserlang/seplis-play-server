from typing import Any, cast
from unittest import mock

import pytest

from seplis_play.schemas.source_metadata_schemas import SourceMetadata
from seplis_play.transcoding.subtitle_transcoder import get_subtitle_file


def subtitle_metadata() -> SourceMetadata:
    return cast(
        SourceMetadata,
        {
            'streams': [
                {
                    'index': 2,
                    'codec_name': 'subrip',
                    'codec_type': 'subtitle',
                    'tags': {'language': 'eng'},
                }
            ],
            'format': {'filename': '/episode.mkv'},
        },
    )


@pytest.mark.asyncio
async def test_get_subtitle_file_maps_the_absolute_stream_index() -> None:
    process = mock.AsyncMock()
    process.returncode = 0
    process.communicate.return_value = (b'WEBVTT\n', b'')
    with mock.patch(
        'asyncio.create_subprocess_exec', return_value=process
    ) as create_process:
        subtitle = await get_subtitle_file(
            metadata=subtitle_metadata(),
            langKey='eng:0',
            offset=0,
            output_format='webvtt',
        )

    assert subtitle == 'WEBVTT\n'
    arguments = cast(Any, create_process).call_args.args
    assert arguments[arguments.index('-map') + 1] == '0:2'
