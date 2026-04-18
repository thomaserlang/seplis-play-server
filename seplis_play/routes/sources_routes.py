from typing import Annotated, Any

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from iso639 import Lang

from seplis_play.scanners.subtitles.subtitle_models import MExternalSubtitle
from seplis_play.schemas.source_schemas import SourceModel, SourceStreamModel

from .. import database, logger
from ..dependencies import get_sources as deps_get_sources
from ..transcoding.base_transcoder import (
    get_video_color,
    get_video_color_bit_depth,
    get_video_stream,
    stream_index_by_lang,
)
from ..utils.browser_media_types_utils import get_browser_media_types

router = APIRouter()


@router.get('/sources', name='Get sources')
async def get_sources_route(
    sources: Annotated[list[dict[str, Any]], Depends(deps_get_sources)],
) -> list[SourceModel]:
    if not sources:
        raise HTTPException(404, 'No sources')
    data: list[SourceModel] = []
    for i, metad in enumerate(sources):
        video = get_video_stream(metad)
        audio_index = stream_index_by_lang(metad, 'audio', None)
        audio = metad['streams'][audio_index.index] if audio_index else None
        if not video:
            raise HTTPException(500, 'No video stream')
        color_range = get_video_color(video)
        media_types = get_browser_media_types(
            metadata=metad,
            video_stream=video,
            audio_stream=audio,
        )
        d = SourceModel(
            width=video['width'],
            height=video['height'],
            codec=video['codec_name'],
            media_type=media_types.media_type,
            duration=metad['format']['duration'],
            video_color_bit_depth=get_video_color_bit_depth(video),
            video_color_range=color_range.range,
            video_color_range_type=color_range.range_type,
            resolution=resolution_text(width=video['width'], height=video['height']),
            index=i,
            size=metad['format']['size'],
            bit_rate=metad['format']['bit_rate'],
            format=metad['format']['format_name'],
        )
        data.append(d)
        for stream in metad['streams']:
            if 'tags' not in stream:
                continue
            title: str | None = stream['tags'].get('title')
            lang: str | None = stream['tags'].get('language')
            if not title and not lang:
                continue
            s = SourceStreamModel(
                title=title,
                language=lang,
                index=stream['index'],
                codec=stream.get('codec_name'),
                default=stream.get('disposition', {}).get('default', 0) == 1,
                forced=stream.get('disposition', {}).get('forced', 0) == 1,
            )
            if stream['codec_type'] == 'audio':
                s.group_index = len(d.audio)
                d.audio.append(s)
            elif stream['codec_type'] == 'subtitle':
                if stream['codec_name'] not in ('dvd_subtitle', 'hdmv_pgs_subtitle'):
                    d.subtitles.append(s)
        await fill_external_subtitles(metad['format']['filename'], d.subtitles)
    return sorted(data, key=lambda x: x.width)


async def fill_external_subtitles(
    filename: str, subtitles: list[SourceStreamModel]
) -> None:
    async with database.session() as session:
        filename = filename.rsplit('.', 1)[0]
        results = await session.scalars(
            sa.select(MExternalSubtitle).where(
                MExternalSubtitle.path.like(f'{filename}.%'),
            )
        )
        for r in results:
            try:
                lang = Lang(r.language)
                name: str = lang.name
                if r.sdh:
                    name += ' (SDH)'
                if r.forced:
                    name += ' (Forced)'
                s = SourceStreamModel(
                    title=name,
                    language=r.language,
                    index=r.id + 1000,
                    codec=r.type,
                    default=r.default,
                    forced=r.forced,
                )
                subtitles.append(s)
            except Exception as e:
                logger.exception(e)


def resolution_text(width: int, height: int) -> str:
    if width <= 256 and height <= 144:
        return '144p'
    if width <= 426 and height <= 240:
        return '240p'
    if width <= 640 and height <= 360:
        return '360p'
    if width <= 854 and height <= 480:
        return '480p'
    if width <= 1280 and height <= 962:
        return '720p'
    if width <= 1920 and height <= 1200:
        return '1080p'
    if width <= 2560 and height <= 1440:
        return '1440p'
    if width <= 4096 and height <= 3072:
        return '4K'
    if width <= 8192 and height <= 6144:
        return '8K'
    return f'{width}x{height}'
