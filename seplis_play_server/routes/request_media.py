from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, RootModel
from urllib.parse import urlencode
from ..transcoders.video import Transcode_settings, Transcoder
from ..dependencies import get_metadata

router = APIRouter()

class Request_media(BaseModel):
    direct_play_url: str
    can_direct_play: bool
    transcode_url: str
    transcode_start_time: float

@router.get('/request-media', response_model=Request_media)
async def request_media(
    source_index: int, 
    settings: Transcode_settings = Depends(),
    metadata = Depends(get_metadata), 
):
    if not metadata:
        raise HTTPException(404, 'No metadata')
    
    t = Transcoder(settings=settings, metadata=metadata[source_index])

    settings_dict = RootModel[Transcode_settings](settings).model_dump(exclude_none=True, exclude_unset=True)
    for key in settings_dict:
        if isinstance(settings_dict[key], list):
            settings_dict[key] = ','.join(settings_dict[key])
    can_copy_video = t.can_copy_video()
    if 'start_time' in settings_dict and can_copy_video:
        settings_dict['start_time'] = t.closest_keyframe_time(settings.start_time)
    format_supported = any(fmt in settings.supported_video_containers \
                           for fmt in metadata[source_index]['format']['format_name'].split(','))
    return Request_media(
        direct_play_url=f'/source?play_id={settings.play_id}&source_index={source_index}',
        can_direct_play=format_supported and can_copy_video and t.can_copy_audio(),
        transcode_url=f'/transcode?source_index={source_index}&{urlencode(settings_dict)}',
        transcode_start_time=settings_dict.get('start_time', 0),
    )