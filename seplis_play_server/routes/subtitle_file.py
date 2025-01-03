from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import StringConstraints

from ..dependencies import get_metadata
from ..transcoders.subtitle import get_subtitle_file, get_subtitle_file_from_external

router = APIRouter()


@router.get('/subtitle-file')
async def download_subtitle(
    lang: Annotated[str, StringConstraints(min_length=1)],
    offset: int | float = 0,
    output_format: Literal['webvtt', 'ass'] = 'webvtt',
    metadata=Depends(get_metadata),
):
    if int(lang.split(':')[1]) < 1000:
        sub = await get_subtitle_file(
            metadata=metadata, lang=lang, offset=offset, output_format=output_format
        )
    else:
        sub = await get_subtitle_file_from_external(
            id_=int(lang.split(':')[1]) - 1000,
            offset=offset,
            output_format=output_format,
        )
    if not sub:
        raise HTTPException(500, 'Unable retrive subtitle file')
    return Response(content=sub, media_type='text/vtt')
