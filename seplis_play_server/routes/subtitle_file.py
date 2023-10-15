from fastapi import APIRouter, HTTPException, Response, Depends
from pydantic import constr
from ..transcoders.subtitle import get_subtitle_file, get_subtitle_file_from_external
from ..dependencies import get_metadata

router = APIRouter()

@router.get('/subtitle-file')
async def download_subtitle(
    source_index: int,
    lang: constr(min_length=1),
    start_time: int | float = 0,
    metadata=Depends(get_metadata)
):    
    if not metadata:
        raise HTTPException(404, 'No metadata')
    if int(lang.split(':')[1]) < 1000:
        sub = await get_subtitle_file(
            metadata=metadata[source_index], 
            lang=lang, 
            start_time=start_time
        )
    else:
        sub = await get_subtitle_file_from_external(
            id_=int(lang.split(':')[1])-1000,
            start_time=start_time,
        )
    if not sub:
        raise HTTPException(500, 'Unable retrive subtitle file')
    return Response(content=sub, media_type='text/vtt')