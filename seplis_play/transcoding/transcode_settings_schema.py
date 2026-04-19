import uuid
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import Query
from pydantic import BeforeValidator, StringConstraints, field_validator
from pydantic.dataclasses import dataclass

CodecOrContainerName = Annotated[
    str, StringConstraints(pattern=r'^[a-z0-9][a-z0-9._-]*$')
]


def _split_query_list(v: list[str] | str) -> list[str]:
    values = v if isinstance(v, list) else [v]
    split_values = []
    for value in values:
        split_values.extend(part.strip() for part in value.split(','))
    return split_values


@dataclass
class TranscodeSettings:
    play_id: Annotated[str, Query(min_length=1)]
    session: Annotated[
        str, Query(default_factory=lambda: str(uuid.uuid4()), min_length=32)
    ]
    supported_hdr_formats: Annotated[
        Annotated[
            list[Literal['hdr10', 'hlg', 'dovi', '']],
            BeforeValidator(_split_query_list),
        ],
        Query(default_factory=lambda: []),
    ]
    supported_audio_codecs: Annotated[
        Annotated[list[CodecOrContainerName], BeforeValidator(_split_query_list)],
        Query(default_factory=lambda: ['aac']),
    ]
    supported_video_containers: Annotated[
        Annotated[list[CodecOrContainerName], BeforeValidator(_split_query_list)],
        Query(default_factory=lambda: ['mp4']),
    ]
    supported_video_codecs: Annotated[
        Annotated[list[CodecOrContainerName], BeforeValidator(_split_query_list)],
        Query(default_factory=lambda: ['h264']),
    ]
    supported_video_color_bit_depth: Annotated[int, Query(ge=8)] = 10
    source_index: int = 0
    format: Literal['hls'] = 'hls'
    transcode_video_codec: Literal['h264', 'hevc', 'av1'] = 'h264'
    transcode_audio_codec: Literal['aac', 'opus', 'dts', 'flac', 'mp3'] = 'aac'

    start_time: Annotated[Decimal, Query()] = Decimal(0)
    start_segment: int | None = None
    audio_lang: str | None = None
    max_audio_channels: int | None = None
    max_width: int | None = None
    max_video_bitrate: int | None = None
    client_can_switch_audio_track: bool = False
    force_transcode: bool = False
    hls_include_all_subtitles: bool = False
    hls_subtitle_lang: str | None = None
    hls_subtitle_offset: Decimal | None = None

    @field_validator('supported_video_color_bit_depth', mode='before')
    @classmethod
    def empty_str_to_default_bit_depth(cls, v: str | int) -> int:
        if v == '':
            return 10
        return int(v)

    @field_validator('start_time', mode='before')
    @classmethod
    def empty_str_to_default_start_time(cls, v: str | Decimal) -> Decimal:
        if v == '':
            return Decimal(0)
        if isinstance(v, str):
            return Decimal(v)
        return v

    @field_validator(
        'max_audio_channels',
        'max_width',
        'max_video_bitrate',
        'start_segment',
        mode='before',
    )
    @classmethod
    def empty_str_to_none(cls, v: str | int | None) -> int | None:
        if v == '':
            return None
        if isinstance(v, str):
            return int(v)
        return v

    @field_validator(
        'supported_video_codecs',
        'supported_audio_codecs',
        'supported_video_containers',
    )
    @classmethod
    def non_empty_list_values(cls, v: list[str]) -> list[str]:
        if any(item == '' for item in v):
            raise ValueError('List items must not be empty')
        return v

    def to_args_dict(self) -> dict:
        from pydantic import RootModel

        settings_dict = RootModel[TranscodeSettings](self).model_dump(
            exclude_none=True, exclude_unset=True
        )
        for key in settings_dict:
            if isinstance(settings_dict[key], list):
                settings_dict[key] = ','.join(settings_dict[key])
        return settings_dict
