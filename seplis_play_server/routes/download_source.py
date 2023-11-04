from mimetypes import guess_type
import os
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from ..dependencies import get_metadata

router = APIRouter()

@router.get('/source', description='Download the source file')
async def download_source(
    source_index: int,
    metadata=Depends(get_metadata),
):    
    if not metadata:
        raise HTTPException(404, 'No metadata')
    if source_index >= len(metadata):
        raise HTTPException(404, 'Source index not found')
    path = metadata[source_index]['format']['filename']
    filename = os.path.basename(path)
    media_type = guess_type(filename)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type, filename=filename)