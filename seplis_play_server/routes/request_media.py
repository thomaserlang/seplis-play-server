from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from urllib.parse import urlencode
from ..transcoders.video import Transcode_settings, Transcoder
from ..dependencies import get_metadata

router = APIRouter()

class Request_media(BaseModel):
    direct_play_url: str
    can_direct_play: bool
    transcode_url: str

@router.get('/request-media', response_model=Request_media)
async def request_media(
    source_index: int, 
    settings: Transcode_settings = Depends(),
    metadata = Depends(get_metadata), 
):
    if not metadata or settings.source_index > len(metadata):
        raise HTTPException(404, 'No metadata')
    
    t = Transcoder(settings=settings, metadata=metadata[source_index])

    video_container_supported = any(fmt in settings.supported_video_containers \
                           for fmt in metadata[source_index]['format']['format_name'].split(','))
    return Request_media(
        direct_play_url=f'/source?play_id={settings.play_id}&source_index={source_index}',
        can_direct_play=video_container_supported and t.can_device_direct_play and t.can_copy_audio,
        transcode_url=f'/hls/media.m3u8?{urlencode(settings.to_args_dict())}',
    )