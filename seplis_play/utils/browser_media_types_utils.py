from pathlib import Path

from pydantic import BaseModel

from seplis_play.schemas.source_metadata_schemas import (
    SourceMetadata,
    SourceMetadataStream,
)


class BrowserMediaTypes(BaseModel):
    media_type: str | None


def get_browser_media_types(
    metadata: SourceMetadata,
    video_stream: SourceMetadataStream | None,
    audio_stream: SourceMetadataStream | None,
) -> BrowserMediaTypes:
    video_mime, audio_mime = get_container_mime_types(metadata)
    video_codec = get_video_codec_string(video_stream)
    audio_codec = get_audio_codec_string(audio_stream, container_mime=audio_mime)

    return BrowserMediaTypes(
        media_type=_format_media_type(video_mime, video_codec, audio_codec),
    )


def get_container_mime_types(metadata: SourceMetadata) -> tuple[str | None, str | None]:
    container = get_container_name(metadata)
    mime_types: dict[str, tuple[str | None, str | None]] = {
        'mp4': ('video/mp4', 'audio/mp4'),
        'webm': ('video/webm', 'audio/webm'),
        'matroska': ('video/x-matroska', 'audio/x-matroska'),
        'ogg': ('video/ogg', 'audio/ogg'),
        'mpegts': ('video/mp2t', 'audio/mp2t'),
    }
    if container is None:
        return (None, None)
    return mime_types.get(container, (None, None))


def get_container_name(metadata: SourceMetadata) -> str | None:
    filename = metadata.get('format', {}).get('filename')
    if filename:
        suffix = Path(filename).suffix.lower()
        if suffix in ('.mp4', '.m4v', '.m4a', '.mov'):
            return 'mp4'
        if suffix == '.webm':
            return 'webm'
        if suffix == '.mkv':
            return 'matroska'
        if suffix in ('.ogg', '.ogv', '.oga'):
            return 'ogg'
        if suffix in ('.ts', '.m2ts'):
            return 'mpegts'

    formats = metadata.get('format', {}).get('format_name', '')
    for format_name in formats.split(','):
        format_name = format_name.strip().lower()
        if format_name in ('mp4', 'mov'):
            return 'mp4'
        if format_name == 'webm':
            return 'webm'
        if format_name in ('matroska', 'mkv'):
            return 'matroska'
        if format_name in ('ogg', 'ogv'):
            return 'ogg'
        if format_name in ('mpegts', 'mpegtsraw'):
            return 'mpegts'

    return None


def get_video_codec_string(stream: SourceMetadataStream | None) -> str | None:
    if not stream:
        return None

    codec = (stream.get('codec_name') or '').lower()
    profile = (stream.get('profile') or '').strip().lower()
    level = stream.get('level')

    if codec == 'h264':
        if profile == 'high':
            prefix = 'avc1.6400'
        elif profile == 'main':
            prefix = 'avc1.4D40'
        elif profile == 'baseline':
            prefix = 'avc1.42E0'
        elif level:
            prefix = 'avc1.4240'
        else:
            return 'avc1'
        return f'{prefix}{int(level):02X}' if level else prefix

    if codec in ('hevc', 'h265'):
        if not level:
            return 'hvc1'
        if profile == 'main 10':
            return f'hvc1.2.4.L{int(level)}.B0'
        return f'hvc1.1.4.L{int(level)}.B0'

    if codec == 'av1':
        return 'av01'
    if codec == 'vp9':
        return 'vp09'

    return codec or None


def get_audio_codec_string(
    stream: SourceMetadataStream | None, container_mime: str | None
) -> str | None:
    if not stream:
        return None

    codec = (stream.get('codec_name') or '').lower()
    profile = (stream.get('profile') or '').strip().lower()

    if codec == 'aac':
        if profile == 'he':
            return 'mp4a.40.5'
        return 'mp4a.40.2'
    if codec == 'ac3':
        return 'ac-3'
    if codec == 'eac3':
        return 'ec-3'
    if codec == 'opus':
        return 'opus'
    if codec == 'vorbis':
        return 'vorbis'
    if codec == 'flac':
        return 'flac'
    if codec == 'mp3':
        if container_mime == 'audio/mp4':
            return 'mp4a.40.34'
        return 'mp3'
    if codec == 'dts':
        return 'dtsc'

    return codec or None


def _format_media_type(mime: str | None, *codecs: str | None) -> str | None:
    if not mime:
        return None
    codec_list = [codec for codec in codecs if codec]
    if not codec_list:
        return mime
    return f'{mime}; codecs="{", ".join(codec_list)}"'
