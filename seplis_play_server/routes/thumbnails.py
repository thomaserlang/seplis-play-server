from fastapi import APIRouter, Request, Depends
from fastapi.staticfiles import StaticFiles
from seplis_play_server import config
from ..dependencies import decode_play_id
from mimetypes import add_type
add_type('image/webp', '.webp')

router = APIRouter()

@router.get('/thumbnails/{image}')
async def get_thumbnail(image: str, request: Request, data = Depends(decode_play_id)):
    if data['type'] == 'series':
        path = f"episode-{data['series_id']}-{data['number']}/{image}"
    elif data['type'] == 'movie':
        path = f"movie-{data['movie_id']}/{image}"
    t = StaticFiles(
        directory=config.thumbnails_path,
    )
    return await t.get_response(path, request.scope)