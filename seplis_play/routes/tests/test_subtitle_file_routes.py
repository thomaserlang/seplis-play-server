from typing import cast
from unittest import mock

import pytest

from seplis_play.routes import subtitle_file_routes
from seplis_play.schemas.source_metadata_schemas import SourceMetadata


def subtitle_metadata() -> SourceMetadata:
    return cast(SourceMetadata, {'format': {'filename': '/episode.mkv'}, 'streams': []})


@pytest.mark.asyncio
async def test_external_subtitle_does_not_query_embedded_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = mock.AsyncMock()
    external = mock.AsyncMock(return_value='WEBVTT\n')
    monkeypatch.setattr(subtitle_file_routes, 'get_cached_subtitle', cache)
    monkeypatch.setattr(subtitle_file_routes, 'get_subtitle_file_from_external', external)

    response = await subtitle_file_routes.download_subtitle_route(
        lang='eng:1001', metadata=subtitle_metadata()
    )

    assert response.body == b'WEBVTT\n'
    cache.assert_not_awaited()
    external.assert_awaited_once_with(id_=1, offset=0, output_format='webvtt')


@pytest.mark.asyncio
async def test_embedded_subtitle_uses_cached_file_and_applies_offset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = mock.AsyncMock(return_value='WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHello')
    live_extract = mock.AsyncMock()
    monkeypatch.setattr(subtitle_file_routes, 'get_cached_subtitle', cache)
    monkeypatch.setattr(subtitle_file_routes, 'get_subtitle_file', live_extract)

    response = await subtitle_file_routes.download_subtitle_route(
        lang='eng:0', metadata=subtitle_metadata(), offset=1
    )

    assert response.body == (b'WEBVTT\n\n00:00:02.000 --> 00:00:03.000\nHello')
    live_extract.assert_not_awaited()
