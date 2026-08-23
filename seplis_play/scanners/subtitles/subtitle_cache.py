import asyncio
import os
import re
import tempfile
from compression import zstd
from pathlib import Path

import sqlalchemy as sa
from iso639 import Lang
from sqlalchemy.ext.asyncio import AsyncSession

from seplis_play import config, database, logger
from seplis_play.schemas.source_metadata_schemas import SourceMetadata
from seplis_play.schemas.source_schemas import SourceStream, source_streams_from_metadata
from seplis_play.transcoding.subtitle_transcoder import get_subtitle_file

from .subtitle_models import MExternalSubtitle


def should_cache_language(language: str) -> bool:
    languages = config.subtitle_cache_languages
    if languages is None:
        return True
    try:
        return Lang(language).pt3 in languages
    except Exception:
        return language.lower() in languages


def required_output_formats(stream: SourceStream) -> tuple[str, ...]:
    if stream.codec in ('ass', 'ssa'):
        return ('webvtt', 'ass')
    return ('webvtt',)


def subtitle_cache_file(
    source_path: str, language: str, stream_index: int, output_format: str
) -> Path:
    media_base = source_path.rsplit('.', 1)[0]
    safe_language = re.sub(r'[^a-zA-Z0-9_-]', '_', language)[:32] or 'und'
    extension = 'vtt' if output_format == 'webvtt' else output_format
    return Path(f'{media_base}.{safe_language}.{stream_index}.{extension}.zst')


def _write_cached_subtitle(path: Path, subtitle: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    compressed = zstd.compress(subtitle.encode('utf-8'))
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
            temporary.write(compressed)
            temporary_path = temporary.name
        os.replace(temporary_path, path)
    finally:
        if temporary_path:
            Path(temporary_path).unlink(missing_ok=True)


def _read_cached_subtitle(path: str) -> str:
    compressed = Path(path).read_bytes()
    return zstd.decompress(compressed).decode('utf-8')


async def get_cached_subtitle(
    metadata: SourceMetadata, lang_key: str, output_format: str
) -> str | None:
    from seplis_play.transcoding.base_transcoder import stream_by_lang

    stream = stream_by_lang(source_streams_from_metadata(metadata, 'subtitle'), lang_key)
    if stream is None:
        return None
    source_path = metadata['format']['filename']
    async with database.session() as session:
        cached = await session.scalar(
            sa.select(MExternalSubtitle).where(
                MExternalSubtitle.source_path == source_path,
                MExternalSubtitle.stream_index == stream.index,
                MExternalSubtitle.type == output_format,
            )
        )
    if cached is None:
        return None
    try:
        return await asyncio.to_thread(_read_cached_subtitle, cached.path)
    except Exception as error:
        logger.warning(f'Unable to read cached subtitle {cached.path}: {error}')
        return None


async def cache_missing_subtitles(metadata: SourceMetadata) -> None:
    source_path = metadata['format']['filename']
    streams = [
        stream
        for stream in source_streams_from_metadata(metadata, 'subtitle')
        if should_cache_language(stream.language)
    ]
    if not streams:
        return

    async with database.session() as session:
        rows = list(
            await session.scalars(
                sa.select(MExternalSubtitle).where(
                    MExternalSubtitle.source_path == source_path
                )
            )
        )
        existing = {(row.stream_index, row.type): row for row in rows}
        for stream in streams:
            if stream.group_index is None:
                continue
            for output_format in required_output_formats(stream):
                cache_key = (stream.index, output_format)
                cached = existing.get(cache_key)
                if cached is not None and os.path.exists(cached.path):
                    continue
                subtitle = await get_subtitle_file(
                    metadata=metadata,
                    langKey=f'{stream.language}:{stream.group_index}',
                    offset=0,
                    output_format=output_format,
                )
                if subtitle is None:
                    continue
                path = subtitle_cache_file(
                    source_path, stream.language, stream.index, output_format
                )
                await asyncio.to_thread(_write_cached_subtitle, path, subtitle)
                if cached is None:
                    cached = MExternalSubtitle(
                        path=str(path),
                        type=output_format,
                        language=stream.language,
                        source_path=source_path,
                        stream_index=stream.index,
                        default=stream.default,
                        forced=stream.forced,
                        sdh=False,
                    )
                    session.add(cached)
                    existing[cache_key] = cached
                else:
                    cached.path = str(path)
                    cached.language = stream.language
                    cached.default = stream.default
                    cached.forced = stream.forced
        await session.commit()


async def delete_cached_subtitles(source_path: str, session: AsyncSession) -> None:
    paths = await session.scalars(
        sa.select(MExternalSubtitle.path).where(
            MExternalSubtitle.source_path == source_path
        )
    )
    for path in paths:
        cached_path = Path(path)
        cached_path.unlink(missing_ok=True)
    await session.execute(
        sa.delete(MExternalSubtitle).where(MExternalSubtitle.source_path == source_path)
    )
