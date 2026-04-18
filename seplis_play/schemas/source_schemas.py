from pydantic import BaseModel


class SourceStreamModel(BaseModel):
    title: str | None
    language: str | None
    index: int
    group_index: int | None = None
    codec: str | None
    default: bool = False
    forced: bool = False


class SourceModel(BaseModel):
    width: int
    height: int
    resolution: str
    codec: str
    media_type: str | None = None
    duration: float
    audio: list[SourceStreamModel] = []
    subtitles: list[SourceStreamModel] = []
    index: int
    video_color_bit_depth: int
    video_color_range: str
    video_color_range_type: str
    size: int | None = None
    bit_rate: int | None = None
    format: str | None = None