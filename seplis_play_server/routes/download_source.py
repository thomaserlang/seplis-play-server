from mimetypes import guess_type
import os
from aiofile import async_open
import anyio
from fastapi import APIRouter, HTTPException, Depends, Request, status
from fastapi.responses import FileResponse, StreamingResponse
from ..dependencies import get_metadata

router = APIRouter()

@router.get('/source', description='Download the source file')
@router.head('/source')
async def download_source(
    request: Request,
    metadata=Depends(get_metadata),
):
    path = metadata['format']['filename']
    filename = os.path.basename(path)
    media_type = guess_type(filename)[0] or "application/octet-stream"

    stat_result = await anyio.to_thread.run_sync(os.stat, path)

    if request.method == 'HEAD':
        return FileResponse(
            path,
            status_code=200, 
            media_type=media_type, 
            filename=filename,
            method='HEAD',
            stat_result=stat_result,
        )

    return range_requests_response(
        request=request,
        path=path,
        filename=filename,
        media_type=media_type,
        stat_result=stat_result,
    )


def range_requests_response(
    request: Request, 
    path: str, 
    filename: str,
    media_type: str,
    stat_result: os.stat_result,    
):
    """Returns StreamingResponse using Range Requests of a given file"""

    file_size = stat_result.st_size
    range_header = request.headers.get("range")

    f = FileResponse(
        path=path, 
        stat_result=stat_result, 
        filename=filename,
        media_type=media_type,
    )
    headers = f.headers
    headers['accept-ranges'] = 'bytes'
    headers['content-encoding'] = 'identity'
    headers['access-control-expose-headers'] = (
        'content-type, accept-ranges, content-length, '
        'content-range, content-encoding'
    )
    headers['cache-control'] = 'no-cache'
    start = 0
    end = file_size - 1
    status_code = status.HTTP_200_OK

    if range_header is not None:
        start, end = _get_range_header(range_header, file_size)
        size = end - start + 1
        headers["content-length"] = str(size)
        headers["content-range"] = f"bytes {start}-{end}/{file_size}"
        status_code = status.HTTP_206_PARTIAL_CONTENT

    return StreamingResponse(
        _send_bytes(path, start, end),
        headers=headers,
        status_code=status_code,
    )


def _get_range_header(range_header: str, file_size: int) -> tuple[int, int]:
    def _invalid_range():
        return HTTPException(
            status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            detail=f"Invalid request range (Range:{range_header!r})",
        )

    try:
        h = range_header.replace("bytes=", "").split("-")
        start = int(h[0]) if h[0] != "" else 0
        end = int(h[1]) if h[1] != "" else file_size - 1
    except ValueError:
        raise _invalid_range()

    if start > end or start < 0 or end > file_size - 1:
        raise _invalid_range()
    return start, end


async def _send_bytes(path: str, start: int, end: int):
    async with async_open(path, mode="rb") as f:
        f.seek(start)
        while (pos := f.tell()) <= end:
            read_size = min(FileResponse.chunk_size, end + 1 - pos)
            yield await f.read(read_size)