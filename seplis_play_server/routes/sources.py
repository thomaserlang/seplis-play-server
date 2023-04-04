from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from ..transcoders.video import get_video_bit_depth, get_video_stream, has_hdr
from ..dependencies import get_metadata

router = APIRouter()

class Response_stream_model(BaseModel):
    title: str
    language: str
    index: int
    codec: str | None
    default: bool = False
    forced: bool = False

class Response_model(BaseModel):
    width: int
    height: int
    codec: str
    duration: float
    audio: list[Response_stream_model] = []
    subtitles: list[Response_stream_model] = []
    index: int
    video_bit_depth: int
    hdr: bool

@router.get('/sources', response_model=list[Response_model])
async def get_sources(metadata = Depends(get_metadata)):
    if not metadata:
        raise HTTPException(404, 'No sources')
    data: list[Response_model] = []
    for i, metad in enumerate(metadata):
        video = get_video_stream(metad)
        if not video:
            raise HTTPException(500, 'No video stream')
        d = Response_model(
            width=video['width'],
            height=video['height'],
            codec=video['codec_name'],
            duration=metad['format']['duration'],
            video_bit_depth=get_video_bit_depth(video),
            hdr=has_hdr(video),
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
            s = Response_stream_model(
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

    