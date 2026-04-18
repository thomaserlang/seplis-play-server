from typing import Literal, NotRequired, TypedDict

type SourceNumber = str | int | float


class SourceStreamTags(TypedDict, total=False):
    language: str
    title: str


class SourceDisposition(TypedDict, total=False):
    default: int
    forced: int


class SourceSideData(TypedDict, total=False):
    side_data_type: str
    dv_profile: int
    rpu_present_flag: int | bool
    bl_present_flag: int | bool
    dv_bl_signal_compatibility_id: int


class SourceBaseStream(TypedDict):
    index: int
    codec_name: str
    disposition: NotRequired[SourceDisposition]
    tags: NotRequired[SourceStreamTags]


class SourceVideoStream(SourceBaseStream):
    codec_type: Literal['video']
    width: int
    height: int
    pix_fmt: str
    profile: NotRequired[str]
    level: NotRequired[int]
    codec_tag_string: NotRequired[str]
    color_transfer: NotRequired[str]
    color_primaries: NotRequired[str]
    r_frame_rate: NotRequired[str]
    has_b_frames: NotRequired[int]
    side_data_list: NotRequired[list[SourceSideData]]


class SourceAudioStream(SourceBaseStream):
    codec_type: Literal['audio']
    channels: int
    sample_rate: NotRequired[str | int]
    profile: NotRequired[str]
    bit_rate: NotRequired[SourceNumber]
    group_index: NotRequired[int]


class SourceSubtitleStream(SourceBaseStream):
    codec_type: Literal['subtitle']


type FFprobeStream = SourceVideoStream | SourceAudioStream | SourceSubtitleStream


class SourceFormat(TypedDict):
    filename: str
    format_name: str
    duration: SourceNumber
    size: SourceNumber
    bit_rate: SourceNumber


class SourceMetadata(TypedDict):
    streams: list[FFprobeStream]
    format: SourceFormat
    keyframes: NotRequired[list[str] | None]
