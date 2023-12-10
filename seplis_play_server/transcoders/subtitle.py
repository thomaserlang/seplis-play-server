import asyncio, os
import sqlalchemy as sa
from typing import Dict
from aiofile import async_open
from seplis_play_server import config, logger, models, database
from .video import stream_index_by_lang, to_subprocess_arguments


async def get_subtitle_file(metadata: Dict, lang: str, offset: int):
    if not lang:
        return
    sub_index = stream_index_by_lang(metadata, 'subtitle', lang)
    if not sub_index:
        return
    args = [
        {'-analyzeduration': '200M'},
        {'-probesize': '200M'},
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
    v = stdout.decode('utf-8')
    return v if not offset else offset_webvtt(v, offset)


async def get_subtitle_file_from_external(id_: int, offset: int):
    
    async with database.session() as session:
        sub_metadata = await session.scalar(sa.select(models.External_subtitle).where(
            models.External_subtitle.id == id_,
        ))
    if not sub_metadata:
        logger.warning(f'Subtitle file could not be found: {id_}')
        return None
    
    if sub_metadata.path.endswith('.vtt'):
        vtt = await get_subtitle_file_from_vtt(sub_metadata.path)
        return vtt if not offset else offset_webvtt(vtt, offset)
    
    if not os.path.exists(sub_metadata.path):
        logger.warning(f'Subtitle file could not be found: {sub_metadata.path}')
        return None

    args = [
        {'-analyzeduration': '200M'},
        {'-probesize': '200M'},
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
    return stdout if not offset else offset_webvtt(stdout, offset)


async def get_subtitle_file_from_vtt(path: str):    
    async with async_open(path, "r") as afp:
        data = await afp.read()
        if not data:
            logger.warning(f'Subtitle file could not be found: {path}')
            return None
        return data


def offset_webvtt(content: str, offset: int):
    lines = content.split('\n')
    output_lines = []
    for line in lines:
        if '-->' in line:
            times = line.split(' --> ')
            if len(times) == 2:
                start_time, end_time = times
                try:
                    start_seconds = sum(float(x) * 60 ** index for index, x in enumerate(reversed(start_time.split(':'))))
                    end_seconds = sum(float(x) * 60 ** index for index, x in enumerate(reversed(end_time.split(':'))))
                    new_start = start_seconds + offset
                    new_end = end_seconds + offset

                    new_start_formatted = '{:02d}:{:02d}:{:06.3f}'.format(int(new_start // 3600),
                                                                           int((new_start % 3600) // 60),
                                                                           new_start % 60)
                    new_end_formatted = '{:02d}:{:02d}:{:06.3f}'.format(int(new_end // 3600),
                                                                         int((new_end % 3600) // 60),
                                                                         new_end % 60)

                    output_lines.append(f"{new_start_formatted} --> {new_end_formatted}")
                except ValueError:
                    output_lines.append(line)
            else:
                output_lines.append(line)
        else:
            output_lines.append(line)

    return '\n'.join(output_lines)