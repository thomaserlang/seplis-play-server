from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from seplis_play.scanners.subtitles.subtitles import get_external_subtitles
from seplis_play.schemas.source_metadata_schemas import SourceMetadata
from seplis_play.schemas.source_schemas import Source

from ..dependencies import get_sources as deps_get_sources

router = APIRouter()


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
        external_subs = await get_external_subtitles(metadata['format']['filename'])
        d.subtitles.extend(external_subs)
    return sorted(data, key=lambda x: x.width)
