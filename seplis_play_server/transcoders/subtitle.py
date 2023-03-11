import asyncio, os
from typing import Dict
from seplis_play_server import config, logger
from .video import stream_index_by_lang, subprocess_env, to_subprocess_arguments

async def get_subtitle_file(metadata: Dict, lang: str, start_time: int, offset: int = None):
    if not lang:
        return
    sub_index = stream_index_by_lang(metadata, 'subtitle', lang)
    if not sub_index:
        return
    if offset and start_time and (offset < 0):
        if start_time > offset:
            start_time += offset
            offset = 0
    args = [
        {'-analyzeduration': '20000000'},
        {'-probesize': '20000000'},
        {'-ss': str(start_time)},
        {'-i': metadata['format']['filename']},
        {'-y': None},
        {'-vn': None},
        {'-an': None},
        {'-c:s': 'webvtt'},
        {'-map': f'0:s:{sub_index.group_index}'},
        {'-f': 'webvtt'},
        {'-': None},
    ]
    if offset:
        args.insert(2, {'-itsoffset': str(offset)})
    args = to_subprocess_arguments(args)        
    logger.debug(f'Subtitle args: {" ".join(args)}')
    process = await asyncio.create_subprocess_exec(
        os.path.join(config.ffmpeg_folder, 'ffmpeg'),
        *args,
        env=subprocess_env(),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        logger.warning(f'Subtitle file could not be exported!: {stderr}')
        return None
    return stdout