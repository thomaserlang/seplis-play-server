import sqlalchemy as sa
from iso639 import Lang
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from ..transcoders.video import get_video_color_bit_depth, get_video_color, get_video_stream
from ..dependencies import get_metadata
from .. import database, models, logger

router = APIRouter()

class Source_stream_model(BaseModel):
    title: str | None
    language: str | None
    index: int
    group_index: int | None
    codec: str | None
    default: bool = False
    forced: bool = False

class Source_model(BaseModel):
    width: int
    height: int
    resolution: str
    codec: str
    duration: float
    audio: list[Source_stream_model] = []
    subtitles: list[Source_stream_model] = []
    index: int
    video_color_bit_depth: int
    video_color_range: str
    video_color_range_type: str
    size: int | None = None
    bit_rate: int | None = None
    format: str | None = None

@router.get('/sources', response_model=list[Source_model])
async def get_sources(metadata = Depends(get_metadata)):
    if not metadata:
        raise HTTPException(404, 'No sources')
    data: list[Source_model] = []
    for i, metad in enumerate(metadata):
        video = get_video_stream(metad)
        if not video:
            raise HTTPException(500, 'No video stream')
        color_range = get_video_color(video)
        d = Source_model(
            width=video['width'],
            height=video['height'],
            codec=video['codec_name'],
            duration=metad['format']['duration'],
            video_color_bit_depth=get_video_color_bit_depth(video),
            video_color_range=color_range.range,
            video_color_range_type=color_range.range_type,
            resolution=resolution_text(width=video['width'], height=video['height']),
            index=i,
            size=metad['format']['size'],
            bit_rate=metad['format']['bit_rate'],
            format=metad['format']['format_name'],
        )
        data.append(d)
        for stream in metad['streams']:
            if 'tags' not in stream:
                continue
            title = stream['tags'].get('title')
            lang = stream['tags'].get('language')
            if not title and not lang:
                continue
            s = Source_stream_model(
                title=title,
                language=lang,
                index=stream['index'],
                codec=stream.get('codec_name'),
                default=stream.get('disposition', {}).get('default', 0) == 1,
                forced=stream.get('disposition', {}).get('forced', 0) == 1,
            )
            if stream['codec_type'] == 'audio':
                d.group_index = len(d.audio)
                d.audio.append(s)
            elif stream['codec_type'] == 'subtitle':
                if stream['codec_name'] not in ('dvd_subtitle', 'hdmv_pgs_subtitle'):
                    d.subtitles.append(s)
        await fill_external_subtitles(metad['format']['filename'], d.subtitles)
    return sorted(data, key=lambda x: x.width)


async def fill_external_subtitles(filename, subtitles: list[Source_stream_model]):
    async with database.session() as session:
        filename = filename.rsplit('.', 1)[0]
        results = await session.scalars(sa.select(models.External_subtitle).where(
            models.External_subtitle.path.like(f'{filename}.%'),
        ))
        for r in results:
            try:
                l = Lang(r.language)
                name = l.name
                if r.sdh:
                    name += ' (SDH)'
                if r.forced:
                    name += ' (Forced)'
                s = Source_stream_model(
                    title=name,
                    language=r.language,
                    index=r.id + 1000,
                    codec=r.type,
                    default=r.default,
                    forced=r.forced,
                )
                subtitles.append(s)
            except Exception as e:
                logger.exception(e)


def resolution_text(width: int, height: int):
    if width <= 256 and height <= 144:
        return '144p'
    elif width <= 426 and height <= 240:
        return '240p'
    elif width <= 640 and height <= 360:
        return '360p'
    elif width <= 854 and height <= 480:
        return '480p'
    elif width <= 1280 and height <= 962:
        return '720p'
    elif width <= 1920 and height <= 1200:
        return '1080p'
    elif width <= 2560 and height <= 1440:
        return '1440p'
    elif width <= 4096 and height <= 3072:
        return '4K'
    elif width <= 8192 and height <= 6144:
        return '8K'
    return f'{width}x{height}'