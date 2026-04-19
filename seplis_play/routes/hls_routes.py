import math
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse

from seplis_play import logger

from .. import config
from ..dependencies import get_metadata
from ..schemas.source_metadata_schemas import SourceMetadata
from ..schemas.source_schemas import Source
from ..transcoding.base_transcoder import TranscodeSettings, sessions
from ..transcoding.hls_transcoder import HlsTranscoder

router = APIRouter()


@router.get('/hls/main.m3u8', name='Get HLS main playlist')
async def get_main_playlist_route(
    settings: Annotated[TranscodeSettings, Depends()],
    metadata: Annotated[SourceMetadata, Depends(get_metadata)],
) -> Response:
    transcoder = HlsTranscoder(settings=settings, metadata=metadata)
    return Response(
        content=await transcoder.generate_main_playlist(),
        media_type='application/x-mpegURL',
    )


@router.get('/hls/media.m3u8', name='Get HLS media playlist')
async def get_media_route(
    settings: Annotated[TranscodeSettings, Depends()],
    metadata: Annotated[SourceMetadata, Depends(get_metadata)],
) -> Response:
    if settings.session in sessions:
        transcoder = HlsTranscoder(settings=settings, metadata=metadata)
    else:
        transcoder = await start_transcode(settings)
    return Response(
        content=transcoder.generate_media_playlist(),
        media_type='application/x-mpegURL',
    )


@router.get('/hls/subtitle.m3u8', name='Get HLS subtitle playlist')
async def get_subtitle_playlist_route(
    play_id: str,
    source_index: int,
    lang: str,
    metadata: Annotated[SourceMetadata, Depends(get_metadata)],
) -> Response:
    duration = Source.from_source_metadata(
        metadata=metadata,
        index=source_index,
    ).duration
    params = urlencode({'play_id': play_id, 'source_index': source_index, 'lang': lang})
    playlist = [
        '#EXTM3U',
        '#EXT-X-VERSION:3',
        f'#EXT-X-TARGETDURATION:{math.ceil(duration)}',
        '#EXT-X-PLAYLIST-TYPE:VOD',
        f'#EXTINF:{duration:.3f},',
        f'/subtitle-file?{params}',
        '#EXT-X-ENDLIST',
    ]
    return Response(content='\n'.join(playlist), media_type='application/x-mpegURL')


@router.get('/hls/media{segment}.m4s', name='Get HLS media segment')
async def get_media_segment_route(
    segment: int,
    settings: Annotated[TranscodeSettings, Depends()],
) -> FileResponse:
    if settings.session in sessions:
        folder: str | None = sessions[settings.session].transcode_folder

        if folder is not None:
            await manage_transcoder_pause(settings.session, folder, segment)
            if await HlsTranscoder.is_segment_ready(folder, segment):
                return FileResponse(HlsTranscoder.get_segment_path(folder, segment))

            (
                first_transcoded_segment,
                last_transcoded_segment,
            ) = await HlsTranscoder.first_last_transcoded_segment(folder)
            upper_bound = (
                last_transcoded_segment
                + config.ffmpeg_segment_threshold_for_new_transcoder
            )
            if first_transcoded_segment <= segment <= upper_bound:
                logger.debug(
                    f'Requested segment {segment} is within the range '
                    f'{first_transcoded_segment}-{upper_bound} '
                    f'to wait for transcoding'
                )
                if await HlsTranscoder.wait_for_segment(folder, segment):
                    return FileResponse(HlsTranscoder.get_segment_path(folder, segment))

            logger.debug(
                f'Requested segment {segment} is not within the range '
                f'{first_transcoded_segment}-{upper_bound} '
                f'to wait for transcoding, start a new transcoder'
            )
    else:
        logger.debug('Start new transcoder since the session does not exist')

    await start_transcode(settings, segment)

    folder = sessions[settings.session].transcode_folder
    if folder is not None and await HlsTranscoder.wait_for_segment(folder, segment):
        return FileResponse(HlsTranscoder.get_segment_path(folder, segment))

    raise HTTPException(404, 'No media')


@router.get('/hls/init.mp4', name='Get HLS init segment')
def get_init_segment_route(
    settings: Annotated[TranscodeSettings, Depends()],
) -> FileResponse:
    p = config.transcode_folder / settings.session / 'init.mp4'
    if not p.is_file():
        raise HTTPException(404, 'No init file')
    return FileResponse(p)


async def start_transcode(
    settings: TranscodeSettings,
    start_segment: int = -1,
) -> HlsTranscoder:
    metadata = await get_metadata(settings.play_id, settings.source_index)
    transcode = HlsTranscoder(settings=settings, metadata=metadata)
    if start_segment == -1:
        transcode.settings.start_segment = transcode.start_segment_from_start_time(
            settings.start_time
        )
        transcode.settings.start_time = transcode.start_time_from_segment(
            transcode.settings.start_segment
        )
    else:
        transcode.settings.start_time = transcode.start_time_from_segment(start_segment)
        transcode.settings.start_segment = start_segment

    ready = await transcode.start()
    if not ready:
        raise HTTPException(500, 'Transcode failed to start')
    sessions[settings.session].segment_time = transcode.segment_time()
    return transcode


async def manage_transcoder_pause(
    session_key: str, folder: str, current_segment: int
) -> None:
    session_model = sessions.get(session_key)
    if not session_model or not session_model.segment_time:
        return
    _, last = await HlsTranscoder.first_last_transcoded_segment(folder)
    if last < 0:
        return
    ahead = last - current_segment
    runner = session_model.ffmpeg_runner
    if not runner.paused and ahead >= config.ffmpeg_pause_threshold_seconds:
        runner.pause()
        logger.info(
            f'[{session_key}] Paused transcoder '
            f'({ahead} segments ahead of {current_segment})'
        )
    elif runner.paused and ahead < config.ffmpeg_resume_threshold_seconds:
        runner.resume()
        logger.info(
            f'[{session_key}] Resumed transcoder '
            f'({ahead} segments ahead of {current_segment})'
        )
