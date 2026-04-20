from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import StringConstraints

from ..dependencies import get_metadata
from ..schemas.source_metadata_schemas import SourceMetadata
from ..transcoding.subtitle_transcoder import (
    get_subtitle_file,
    get_subtitle_file_from_external,
)

router = APIRouter()


@router.get('/subtitle-file', name='Download subtitle file')
async def download_subtitle_route(
    lang: Annotated[str, StringConstraints(min_length=1)],
    metadata: Annotated[SourceMetadata, Depends(get_metadata)],
    offset: int | float = 0,
    output_format: Literal['webvtt', 'ass'] = 'webvtt',
) -> Response:
    _, group_index = lang.split(':')
    if not group_index.isdigit():
        raise HTTPException(400, 'Invalid group index')
    group_index = int(group_index)
    sub: str | None
    if group_index < 1000:
        sub = await get_subtitle_file(
            metadata=metadata, langKey=lang, offset=offset, output_format=output_format
        )
    else:
        sub = await get_subtitle_file_from_external(
            id_=group_index - 1000,
            offset=offset,
            output_format=output_format,
        )
    if not sub:
        raise HTTPException(500, 'Unable retrive subtitle file')
    return Response(
        content=sub, media_type='text/vtt' if output_format == 'webvtt' else 'text/x-ass'
    )
