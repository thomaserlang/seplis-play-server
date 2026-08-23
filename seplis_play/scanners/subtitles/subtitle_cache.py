import sqlalchemy as sa
from iso639 import Lang
from sqlalchemy.ext.asyncio import AsyncSession

from seplis_play import config, database
from seplis_play.schemas.source_metadata_schemas import SourceMetadata
from seplis_play.schemas.source_schemas import SourceStream, source_streams_from_metadata
from seplis_play.transcoding.subtitle_transcoder import get_subtitle_file

from .subtitle_cache_models import MCachedSubtitle


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


async def get_cached_subtitle(
    metadata: SourceMetadata, lang_key: str, output_format: str
) -> str | None:
    from seplis_play.transcoding.base_transcoder import stream_by_lang

    stream = stream_by_lang(source_streams_from_metadata(metadata, 'subtitle'), lang_key)
    if stream is None:
        return None
    source_path = metadata['format']['filename']
    async with database.session() as session:
        return await session.scalar(
            sa.select(MCachedSubtitle.content).where(
                MCachedSubtitle.source_path == source_path,
                MCachedSubtitle.stream_index == stream.index,
                MCachedSubtitle.type == output_format,
            )
        )


async def cache_missing_subtitles(metadata: SourceMetadata) -> None:
    source_path = metadata['format']['filename']
    streams = [
        stream
        for stream in source_streams_from_metadata(metadata, 'subtitle')
        if should_cache_language(stream.language)
    ]
    desired = {
        (stream.index, output_format)
        for stream in streams
        for output_format in required_output_formats(stream)
    }

    async with database.session() as session:
        rows = list(
            await session.scalars(
                sa.select(MCachedSubtitle).where(
                    MCachedSubtitle.source_path == source_path
                )
            )
        )
        existing = {(row.stream_index, row.type): row for row in rows}
        for cache_key, row in tuple(existing.items()):
            if cache_key not in desired:
                await session.delete(row)
                del existing[cache_key]
        for stream in streams:
            if stream.group_index is None:
                continue
            for output_format in required_output_formats(stream):
                cache_key = (stream.index, output_format)
                cached = existing.get(cache_key)
                if cached is not None and cached.content is not None:
                    continue
                if cached is None:
                    cached = MCachedSubtitle(
                        source_path=source_path,
                        stream_index=stream.index,
                        type=output_format,
                        language=stream.language,
                        default=stream.default,
                        forced=stream.forced,
                        content=None,
                    )
                    session.add(cached)
                    existing[cache_key] = cached
                subtitle = await get_subtitle_file(
                    metadata=metadata,
                    langKey=f'{stream.language}:{stream.group_index}',
                    offset=0,
                    output_format=output_format,
                )
                if subtitle is None:
                    continue
                cached.content = subtitle
                cached.language = stream.language
                cached.default = stream.default
                cached.forced = stream.forced
        await session.commit()


async def delete_cached_subtitles(source_path: str, session: AsyncSession) -> None:
    await session.execute(
        sa.delete(MCachedSubtitle).where(MCachedSubtitle.source_path == source_path)
    )
