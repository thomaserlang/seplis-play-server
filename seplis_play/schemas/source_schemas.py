from dataclasses import field
from decimal import Decimal

from pydantic.dataclasses import dataclass

from seplis_play.schemas.source_metadata_schemas import SourceMetadata, SourceNumber


@dataclass
class SourceStream:
    title: str | None
    language: str | None
    index: int
    codec: str | None
    group_index: int | None = None
    default: bool = False
    forced: bool = False


@dataclass
class Source:
    width: int
    height: int
    resolution: str
    codec: str
    duration: Decimal
    index: int
    video_color_bit_depth: int
    video_color_range: str
    video_color_range_type: str
    bitrate: int
    media_type: str | None = None
    audio: list[SourceStream] = field(default_factory=list)
    subtitles: list[SourceStream] = field(default_factory=list)
    size: int | None = None
    format: str | None = None
    fps: Decimal = Decimal(0)
    pixel_format: str = ''
    color_transfer: str = ''
    color_primaries: str = ''

    @classmethod
    def from_source_metadata(cls, metadata: SourceMetadata, index: int) -> Source:
        from seplis_play.transcoding.base_transcoder import (
            get_video_color,
            get_video_color_bit_depth,
            get_video_stream,
            stream_index_by_lang,
        )
        from seplis_play.utils.browser_media_types_utils import get_browser_media_types

        video = get_video_stream(metadata)
        audio_index = stream_index_by_lang(metadata, 'audio', None)
        audio = metadata['streams'][audio_index.index] if audio_index else None
        color_range = get_video_color(video)
        media_types = get_browser_media_types(
            metadata=metadata,
            video_stream=video,
            audio_stream=audio,
        )

        source = cls(
            width=video['width'],
            height=video['height'],
            codec=video['codec_name'],
            media_type=media_types.media_type,
            duration=source_decimal(metadata['format']['duration']),
            video_color_bit_depth=get_video_color_bit_depth(video),
            video_color_range=color_range.range,
            video_color_range_type=color_range.range_type,
            resolution=resolution_text(width=video['width'], height=video['height']),
            index=index,
            size=source_int(metadata['format']['size']),
            bitrate=source_int(metadata['format']['bit_rate']),
            format=metadata['format']['format_name'],
            fps=source_fps(video.get('r_frame_rate')),
        )

        for stream in metadata['streams']:
            tags = stream.get('tags')
            if not tags:
                continue
            title = tags.get('title')
            lang = tags.get('language')
            if not title and not lang:
                continue

            source_stream = SourceStream(
                title=title,
                language=lang,
                index=stream['index'],
                codec=stream.get('codec_name'),
                default=stream.get('disposition', {}).get('default', 0) == 1,
                forced=stream.get('disposition', {}).get('forced', 0) == 1,
            )
            if stream['codec_type'] == 'audio':
                source_stream.group_index = len(source.audio)
                source.audio.append(source_stream)
            elif stream['codec_type'] == 'subtitle' and stream['codec_name'] not in (
                'dvd_subtitle',
                'hdmv_pgs_subtitle',
            ):
                source.subtitles.append(source_stream)

        return source


def resolution_text(width: int, height: int) -> str:
    if width <= 256 and height <= 144:
        return '144p'
    if width <= 426 and height <= 240:
        return '240p'
    if width <= 640 and height <= 360:
        return '360p'
    if width <= 854 and height <= 480:
        return '480p'
    if width <= 1280 and height <= 962:
        return '720p'
    if width <= 1920 and height <= 1200:
        return '1080p'
    if width <= 2560 and height <= 1440:
        return '1440p'
    if width <= 4096 and height <= 3072:
        return '4K'
    if width <= 8192 and height <= 6144:
        return '8K'
    return f'{width}x{height}'


def source_float(value: SourceNumber) -> float:
    return float(value)


def source_int(value: SourceNumber) -> int:
    return int(float(value))


def source_decimal(value: SourceNumber) -> Decimal:
    return Decimal(str(value))


def source_fps(value: str | None) -> Decimal:
    if not value or '/' not in value:
        return Decimal(0)
    num, den = value.split('/', 1)
    denominator = Decimal(den)
    if denominator <= 0:
        return Decimal(0)
    return Decimal(num) / denominator
