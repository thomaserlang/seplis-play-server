from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel


class PlaybackMethod(StrEnum):
    DIRECT_PLAY = 'direct_play'
    REMUX = 'remux'
    TRANSCODE = 'transcode'


class OutputFormat(StrEnum):
    HLS = 'hls'


class DecisionScope(StrEnum):
    PLAYBACK = 'playback'
    VIDEO = 'video'
    AUDIO = 'audio'
    CONTAINER = 'container'


class StreamKind(StrEnum):
    VIDEO = 'video'
    AUDIO = 'audio'


class StreamAction(StrEnum):
    COPY = 'copy'
    TRANSCODE = 'transcode'


class LimitKind(StrEnum):
    AUDIO_CHANNELS = 'audio_channels'
    VIDEO_BITRATE = 'video_bitrate'
    WIDTH = 'width'
    VIDEO_BIT_DEPTH = 'video_bit_depth'


class BlockerCode(StrEnum):
    FORCED = 'forced'
    UNSUPPORTED_CODEC = 'unsupported_codec'
    UNSUPPORTED_HDR = 'unsupported_hdr'
    LIMIT_EXCEEDED = 'limit_exceeded'
    MISSING_KEYFRAMES = 'missing_keyframes'
    VIDEO_TRANSCODE_REQUIRES_AUDIO_TRANSCODE = (
        'video_transcode_requires_audio_transcode'
    )
    UNSUPPORTED_CONTAINER = 'unsupported_container'
    AUDIO_TRACK_SWITCH_UNSUPPORTED = 'audio_track_switch_unsupported'


@dataclass(frozen=True, slots=True)
class DecisionBlocker:
    code: BlockerCode
    scope: DecisionScope
    stream: StreamKind | None = None
    source_codec: str | None = None
    target_codec: str | None = None
    source_container: str | None = None
    source_hdr: str | None = None
    limit_kind: LimitKind | None = None
    limit: int | None = None
    actual: int | None = None


class DecisionCheck(BaseModel):
    supported: bool
    blockers: list[DecisionBlocker]


@dataclass(frozen=True, slots=True)
class DirectPlayDecision:
    supported: bool
    blockers: tuple[DecisionBlocker, ...]


@dataclass(frozen=True, slots=True)
class StreamDecision:
    kind: StreamKind
    action: StreamAction
    source_codec: str
    target_codec: str
    blockers: tuple[DecisionBlocker, ...]


@dataclass(frozen=True, slots=True)
class TranscodeDecision:
    session: str
    method: PlaybackMethod
    target_format: OutputFormat
    required: bool
    direct_play: DirectPlayDecision
    video: StreamDecision
    audio: StreamDecision


def format_blocker(blocker: DecisionBlocker) -> str:
    fields = [
        ('scope', blocker.scope.value),
        ('stream', blocker.stream.value if blocker.stream else None),
        ('source_codec', blocker.source_codec),
        ('target_codec', blocker.target_codec),
        ('source_container', blocker.source_container),
        ('source_hdr', blocker.source_hdr),
        ('limit_kind', blocker.limit_kind.value if blocker.limit_kind else None),
        ('limit', blocker.limit),
        ('actual', blocker.actual),
    ]
    facts = [f'{key}={value}' for key, value in fields if value is not None]
    return f'{blocker.code.value}({", ".join(facts)})'
