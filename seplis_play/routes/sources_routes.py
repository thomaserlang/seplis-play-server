from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from iso639 import Lang

from seplis_play.scanners.subtitles.subtitle_models import MExternalSubtitle
from seplis_play.schemas.source_metadata_schemas import SourceMetadata
from seplis_play.schemas.source_schemas import Source, SourceStream
from seplis_play.schemas.source_schemas import resolution_text as source_resolution_text

from .. import database, logger
from ..dependencies import get_sources as deps_get_sources

router = APIRouter()
resolution_text = source_resolution_text


@router.get('/sources', name='Get sources')
async def get_sources_route(
    sources: Annotated[list[SourceMetadata], Depends(deps_get_sources)],
) -> list[Source]:
    if not sources:
        raise HTTPException(404, 'No sources')
    data: list[Source] = []
    for i, metadata in enumerate(sources):
        d = Source.from_source_metadata(metadata=metadata, index=i)
        data.append(d)
        await fill_external_subtitles(metadata['format']['filename'], d.subtitles)
    return sorted(data, key=lambda x: x.width)


async def fill_external_subtitles(filename: str, subtitles: list[SourceStream]) -> None:
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
                s = SourceStream(
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
