from mimetypes import add_type
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from seplis_play import config
from seplis_play.schemas import PlayId

from ..dependencies import decode_play_id

add_type('image/webp', '.webp')

router = APIRouter()


@router.get('/thumbnails/{image}', name='Get thumbnail')
async def get_thumbnail_route(
    image: str,
    request: Request,
    data: Annotated[PlayId, Depends(decode_play_id)],
) -> Response:
    if data.type == 'series':
        path = f'episode-{data.series_id}-{data.number}/{image}'
    else:
        path = f'movie-{data.movie_id}/{image}'
    t = StaticFiles(directory=config.thumbnails_path)
    return await t.get_response(path, request.scope)
