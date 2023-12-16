from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from urllib.parse import urlencode
from ..transcoders.video import Transcode_settings, Transcoder
from ..dependencies import get_metadata

router = APIRouter()

class Request_media(BaseModel):
    direct_play_url: str
    can_direct_play: bool
    hls_url: str
    keep_alive_url: str
    close_session_url: str

@router.get('/request-media', response_model=Request_media)
async def request_media(
    source_index: int, 
    settings: Transcode_settings = Depends(),
    metadata = Depends(get_metadata), 
):
    t = Transcoder(settings=settings, metadata=metadata)

    return Request_media(
        direct_play_url=f'/source?play_id={settings.play_id}&source_index={source_index}',
        can_direct_play=t.get_can_device_direct_play() and t.can_copy_audio,
        hls_url=f'/hls/media.m3u8?{urlencode(settings.to_args_dict())}',
        keep_alive_url=f'/keep-alive/{settings.session}',
        close_session_url=f'/close-session/{settings.session}',
    )