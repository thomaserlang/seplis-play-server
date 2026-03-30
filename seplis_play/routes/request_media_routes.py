from typing import Annotated, Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..dependencies import get_metadata
from ..transcoders.base_transcoder import Transcoder, TranscodeSettings

router = APIRouter()


class RequestMedia(BaseModel):
    direct_play_url: str
    can_direct_play: bool
    hls_url: str
    keep_alive_url: str
    close_session_url: str


@router.get('/request-media', name='Request media')
async def request_media_route(
    source_index: int,
    settings: Annotated[TranscodeSettings, Depends()],
    metadata: Annotated[dict[str, Any], Depends(get_metadata)],
) -> RequestMedia:
    t = Transcoder(settings=settings, metadata=metadata)

    return RequestMedia(
        direct_play_url=f'/source?play_id={settings.play_id}&source_index={source_index}',
        can_direct_play=t.get_can_device_direct_play() and t.can_copy_audio,
        hls_url=f'/hls/media.m3u8?{urlencode(settings.to_args_dict())}',
        keep_alive_url=f'/keep-alive/{settings.session}',
        close_session_url=f'/close-session/{settings.session}',
    )
