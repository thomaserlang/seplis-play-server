import asyncio, os
import sqlalchemy as sa
from typing import Dict
from aiofile import async_open
from seplis_play_server import config, logger, models, database
from .video import stream_index_by_lang, to_subprocess_arguments

async def get_subtitle_file(metadata: Dict, lang: str, start_time: int):
    if not lang:
        return
    sub_index = stream_index_by_lang(metadata, 'subtitle', lang)
    if not sub_index:
        return
    args = [
        {'-analyzeduration': '200M'},
        {'-probesize': '200M'},
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
    args = to_subprocess_arguments(args)        
    logger.debug(f'Subtitle args: {" ".join(args)}')
    process = await asyncio.create_subprocess_exec(
        os.path.join(config.ffmpeg_folder, 'ffmpeg'),
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        logger.warning(f'Subtitle file could not be exported!: {stderr}')
        return None
    return stdout


async def get_subtitle_file_from_external(id_: int, start_time: int):
    
    async with database.session() as session:
        sub_metadata = await session.scalar(sa.select(models.External_subtitle).where(
            models.External_subtitle.id == id_,
        ))
    if not sub_metadata:
        logger.warning(f'Subtitle file could not be found: {id_}')
        return None
    
    if sub_metadata.path.endswith('.vtt'):
        return await get_subtitle_file_from_vtt(sub_metadata.path)
    
    if not os.path.exists(sub_metadata.path):
        logger.warning(f'Subtitle file could not be found: {sub_metadata.path}')
        return None

    args = [
        {'-analyzeduration': '200M'},
        {'-probesize': '200M'},
        {'-ss': str(start_time)},
        {'-i': sub_metadata.path},
        {'-y': None},
        {'-vn': None},
        {'-an': None},
        {'-c:s': 'webvtt'},
        {'-f': 'webvtt'},
        {'-': None},
    ]
    args = to_subprocess_arguments(args)        
    logger.debug(f'Subtitle args: {" ".join(args)}')
    process = await asyncio.create_subprocess_exec(
        os.path.join(config.ffmpeg_folder, 'ffmpeg'),
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        logger.warning(f'Subtitle file could not be exported!: {stderr}')
        return None
    return stdout


async def get_subtitle_file_from_vtt(path: str):    
    async with async_open(path, "r") as afp:
        data = await afp.read()
        if not data:
            logger.warning(f'Subtitle file could not be found: {path}')
            return None
        return data
