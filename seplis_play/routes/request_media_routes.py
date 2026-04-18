from typing import Annotated, Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from seplis_play.transcoding.transcode_settings_schema import TranscodeSettings

from ..dependencies import get_metadata
from ..transcoding.base_transcoder import TranscodeDecision, Transcoder

router = APIRouter()


class RequestMedia(BaseModel):
    direct_play_url: str
    can_direct_play: bool
    hls_url: str
    keep_alive_url: str
    close_session_url: str
    transcode_decision: TranscodeDecision


@router.get('/request-media', name='Request media')
async def request_media_route(
    source_index: int,
    settings: Annotated[TranscodeSettings, Depends()],
    metadata: Annotated[dict[str, Any], Depends(get_metadata)],
) -> RequestMedia:
    t = Transcoder(settings=settings, metadata=metadata)
    hls_file = 'main' if settings.include_subtitles else 'media'
    return RequestMedia(
        direct_play_url=f'/source?play_id={settings.play_id}&source_index={source_index}',
        can_direct_play=t.transcode_decision.direct_play.supported,
        hls_url=f'/hls/{hls_file}.m3u8?{urlencode(settings.to_args_dict())}',
        keep_alive_url=f'/keep-alive/{settings.session}',
        close_session_url=f'/close-session/{settings.session}',
        transcode_decision=t.transcode_decision,
    )
