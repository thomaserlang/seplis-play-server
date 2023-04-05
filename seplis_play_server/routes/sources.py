from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from ..transcoders.video import get_video_color_bit_depth, get_video_color, get_video_stream
from ..dependencies import get_metadata

router = APIRouter()

class Source_stream_model(BaseModel):
    title: str | None
    language: str | None
    index: int
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
                d.audio.append(s)
            elif stream['codec_type'] == 'subtitle':
                if stream['codec_name'] not in ('dvd_subtitle', 'hdmv_pgs_subtitle'):
                    d.subtitles.append(s)
    return sorted(data, key=lambda x: x.width)


def resolution_text(width: int, height: int):
    if width <= 256 and height <= 144:
        return '144p'
    elif width <= 426 and height <= 240:
        return '240p'
    elif width <= 640 and height <= 360:
        return '360p'
    elif width <= 682 and height <= 384:
        return '384p'
    elif width <= 720 and height <= 404:
        return '404p'
    elif width <= 854 and height <= 480:
        return '480p'
    elif width <= 960 and height <= 544:
        return '540p'
    elif width <= 1024 and height <= 576:
        return '576p'
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