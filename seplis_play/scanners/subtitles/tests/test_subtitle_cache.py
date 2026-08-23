from compression import zstd
from pathlib import Path
from typing import cast
from unittest import mock

import pytest
import sqlalchemy as sa

from seplis_play import config
from seplis_play.database import Database
from seplis_play.scanners.subtitles.subtitle_cache import (
    cache_missing_subtitles,
    delete_cached_subtitles,
    get_cached_subtitle,
)
from seplis_play.scanners.subtitles.subtitle_cache_models import MCachedSubtitle
from seplis_play.schemas.source_metadata_schemas import SourceMetadata


def subtitle_metadata(source_path: str) -> SourceMetadata:
    return cast(
        SourceMetadata,
        {
            'streams': [
                {
                    'index': 2,
                    'codec_name': 'subrip',
                    'codec_type': 'subtitle',
                    'tags': {'language': 'eng'},
                },
                {
                    'index': 3,
                    'codec_name': 'subrip',
                    'codec_type': 'subtitle',
                    'tags': {'language': 'dan'},
                },
                {
                    'index': 4,
                    'codec_name': 'ass',
                    'codec_type': 'subtitle',
                    'tags': {'language': 'jpn'},
                },
            ],
            'format': {'filename': source_path},
        },
    )


@pytest.mark.asyncio
async def test_cache_adds_only_missing_configured_languages(
    play_db_test: Database,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, 'subtitle_cache_languages', ['en', 'ja'])
    assert config.subtitle_cache_languages == ['eng', 'jpn']
    extract = mock.AsyncMock(
        side_effect=lambda metadata, langKey, offset, output_format: (
            f'{langKey}:{output_format}'
        )
    )
    monkeypatch.setattr(
        'seplis_play.scanners.subtitles.subtitle_cache.get_subtitle_file', extract
    )
    source_path = str(tmp_path / 'episode.mkv')
    metadata = subtitle_metadata(source_path)

    await cache_missing_subtitles(metadata)
    assert extract.await_count == 3

    async with play_db_test.session() as session:
        cached_english = await session.scalar(
            sa.select(MCachedSubtitle).where(
                MCachedSubtitle.stream_index == 2,
                MCachedSubtitle.type == 'webvtt',
            )
        )
        assert cached_english is not None
        assert cached_english.content == 'eng:0:webvtt'
        cached_english.content = None
        await session.commit()

    await cache_missing_subtitles(metadata)
    assert extract.await_count == 4

    await cache_missing_subtitles(metadata)
    assert extract.await_count == 4

    config.subtitle_cache_languages = ['en', 'da', 'ja']
    await cache_missing_subtitles(metadata)
    assert extract.await_count == 5

    async with play_db_test.session() as session:
        rows = list(
            await session.scalars(
                sa.select(MCachedSubtitle).order_by(
                    MCachedSubtitle.stream_index, MCachedSubtitle.type
                )
            )
        )
    assert [(row.stream_index, row.type) for row in rows] == [
        (2, 'webvtt'),
        (3, 'webvtt'),
        (4, 'ass'),
        (4, 'webvtt'),
    ]
    assert all(row.content is not None for row in rows)
    assert await get_cached_subtitle(metadata, 'eng:0', 'webvtt') == 'eng:0:webvtt'

    async with play_db_test.session() as session:
        compressed = await session.scalar(
            sa.text(
                'SELECT content FROM cached_subtitles '
                "WHERE stream_index = 2 AND type = 'webvtt'"
            )
        )
    assert isinstance(compressed, bytes)
    assert compressed != b'eng:0:webvtt'
    assert zstd.decompress(compressed) == b'eng:0:webvtt'

    config.subtitle_cache_languages = ['eng']
    await cache_missing_subtitles(metadata)
    async with play_db_test.session() as session:
        rows = list(await session.scalars(sa.select(MCachedSubtitle)))
    assert [(row.stream_index, row.type) for row in rows] == [(2, 'webvtt')]

    async with play_db_test.session() as session:
        await delete_cached_subtitles(source_path, session)
        await session.commit()
        assert await session.scalar(sa.select(MCachedSubtitle)) is None


@pytest.mark.asyncio
async def test_failed_extraction_remains_a_cache_miss(
    play_db_test: Database,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, 'subtitle_cache_languages', ['eng'])
    extract = mock.AsyncMock(return_value=None)
    monkeypatch.setattr(
        'seplis_play.scanners.subtitles.subtitle_cache.get_subtitle_file', extract
    )
    metadata = subtitle_metadata(str(tmp_path / 'episode.mkv'))

    await cache_missing_subtitles(metadata)

    async with play_db_test.session() as session:
        cached = await session.scalar(sa.select(MCachedSubtitle))
        assert cached is not None
        assert cached.content is None
    assert await get_cached_subtitle(metadata, 'eng:0', 'webvtt') is None

    await cache_missing_subtitles(metadata)
    assert extract.await_count == 2
