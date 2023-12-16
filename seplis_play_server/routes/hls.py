import os.path
from fastapi import APIRouter, HTTPException, Depends, Response
from fastapi.responses import FileResponse

from seplis_play_server import logger

from .. import config
from ..dependencies import get_metadata
from ..transcoders.video import Transcode_settings, sessions
from ..transcoders.hls import Hls_transcoder

router = APIRouter()

@router.get('/hls/main.m3u8')
async def get_main(
    settings: Transcode_settings = Depends(),
    metadata = Depends(get_metadata),
):
    transcoder = Hls_transcoder(settings=settings, metadata=metadata)
    return Response(
        content=transcoder.generate_main_playlist(),
        media_type='application/x-mpegURL',
    )

@router.get('/hls/media.m3u8')
async def get_media(
    settings: Transcode_settings = Depends(),
    metadata = Depends(get_metadata),
):
    if settings.session in sessions:
        transcoder = Hls_transcoder(settings=settings, metadata=metadata)
    else:
        transcoder = await start_transcode(settings)
    return Response(
        content=transcoder.generate_media_playlist(),
        media_type='application/x-mpegURL',
    )

@router.get('/hls/media{segment}.m4s')
async def get_media_segment(
    segment: int,
    settings: Transcode_settings = Depends(),
):
    if settings.session in sessions:
        folder = sessions[settings.session].transcode_folder

        if await Hls_transcoder.is_segment_ready(folder, segment):
            return FileResponse(Hls_transcoder.get_segment_path(folder, segment))
        
        # If the segment is within 15 segments of the last transcoded segment
        # then wait for the segment to be transcoded.
        wait_for_segments = 7
        first_transcoded_segment, last_transcoded_segment = \
            await Hls_transcoder.first_last_transcoded_segment(folder)
        if first_transcoded_segment <= segment and (last_transcoded_segment + wait_for_segments) >= segment:
            logger.debug(f'Requested segment {segment} is within the range {first_transcoded_segment}-{last_transcoded_segment+wait_for_segments} to wait for transcoding')
            if await Hls_transcoder.wait_for_segment(folder, segment):
                return FileResponse(Hls_transcoder.get_segment_path(folder, segment))
    
        logger.debug(f'Requested segment {segment} is not within the range {first_transcoded_segment}-{last_transcoded_segment+wait_for_segments} to wait for transcoding, start a new transcoder')
    else:
        logger.debug(f'Start new transcoder since the session does not exist')

    await start_transcode(settings, segment)
    
    folder = sessions[settings.session].transcode_folder
    if await Hls_transcoder.wait_for_segment(folder, segment):
        return FileResponse(Hls_transcoder.get_segment_path(folder, segment))
    
    raise HTTPException(404, 'No media')

@router.get('/hls/init.mp4')
def get_init(
    settings: Transcode_settings = Depends(),
):
    try:
        return FileResponse(os.path.join(
            config.transcode_folder, 
            settings.session, 
            'init.mp4',
        ))
    except:
        raise HTTPException(404, 'No init file')

async def start_transcode(settings: Transcode_settings, start_segment: int = -1):
    metadata = await get_metadata(settings.play_id, settings.source_index)
    transcode = Hls_transcoder(settings=settings, metadata=metadata)
    if start_segment == -1:
        transcode.settings.start_segment = transcode.start_segment_from_start_time(settings.start_time)
        transcode.settings.start_time = transcode.start_time_from_segment(transcode.settings.start_segment)
    else:
        transcode.settings.start_time = transcode.start_time_from_segment(start_segment)
        transcode.settings.start_segment = start_segment
    
    ready = await transcode.start()
    if ready == False:
        raise HTTPException(500, 'Transcode failed to start')
    return transcode