import os
from collections.abc import AsyncGenerator
from mimetypes import guess_type
from typing import Annotated, Any

from aiofile import async_open
from anyio import to_thread
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, StreamingResponse

from ..dependencies import get_metadata

router = APIRouter()


@router.get('/source', description='Download the source file', name='Download source')
@router.head('/source', name='Download source (HEAD)')
async def download_source_route(  # noqa: ANN201
    request: Request,
    metadata: Annotated[dict[str, Any], Depends(get_metadata)],
):
    path: str = metadata['format']['filename']
    filename: str = os.path.basename(path)
    media_type: str = guess_type(filename)[0] or 'application/octet-stream'

    stat_result = await to_thread.run_sync(os.stat, path)

    if request.method == 'HEAD':
        return FileResponse(
            path,
            status_code=200,
            media_type=media_type,
            filename=filename,
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
) -> StreamingResponse:
    """Returns StreamingResponse using Range Requests of a given file"""

    file_size: int = stat_result.st_size
    range_header: str | None = request.headers.get('range')

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
        'content-type, accept-ranges, content-length, content-range, content-encoding'
    )
    headers['cache-control'] = 'no-cache'
    start: int = 0
    end: int = file_size - 1
    status_code: int = status.HTTP_200_OK

    if range_header is not None:
        start, end = _get_range_header(range_header, file_size)
        size = end - start + 1
        headers['content-length'] = str(size)
        headers['content-range'] = f'bytes {start}-{end}/{file_size}'
        status_code = status.HTTP_206_PARTIAL_CONTENT

    return StreamingResponse(
        _send_bytes(path, start, end),
        headers=headers,
        status_code=status_code,
    )


def _get_range_header(range_header: str, file_size: int) -> tuple[int, int]:
    def _invalid_range() -> HTTPException:
        return HTTPException(
            status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            detail=f'Invalid request range (Range:{range_header!r})',
        )

    try:
        h = range_header.replace('bytes=', '').split('-')
        start: int = int(h[0]) if h[0] != '' else 0
        end: int = int(h[1]) if h[1] != '' else file_size - 1
    except ValueError:
        raise _invalid_range() from None

    if start > end or start < 0 or end > file_size - 1:
        raise _invalid_range()
    return start, end


async def _send_bytes(path: str, start: int, end: int) -> AsyncGenerator[bytes]:
    async with async_open(path, mode='rb') as f:
        f.seek(start)
        while (pos := f.tell()) <= end:
            read_size = min(FileResponse.chunk_size, end + 1 - pos)
            yield await f.read(read_size)
