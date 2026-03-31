from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass
class TranscodeProgress:
    frame: int = 0
    fps: Decimal = Decimal(0)
    bitrate: str = '0kbits/s'
    total_size: int = 0
    time: Decimal = Decimal(0)
    speed: float = 0.0
    percent: Decimal = Decimal(0)
    stage: str = 'transcoding'  # transcoding, remuxing, finalizing


@dataclass
class MediaInfo:
    duration: Decimal = Decimal(0)
    width: int = 0
    height: int = 0
    video_codec: str = ''
    audio_codec: str = ''
    bitrate: int = 0
    fps: Decimal = Decimal(0)
    # Extended info for smart transcoding
    pixel_format: str = ''
    color_transfer: str = ''
    color_primaries: str = ''
    audio_channels: int = 2
    audio_sample_rate: int = 48000
    is_hdr: bool = False
    is_10bit: bool = False
    has_bframes: bool = True

    @classmethod
    def from_ffprobe(cls, data: dict[str, Any]) -> MediaInfo:
        info = MediaInfo()

        if 'format' in data:
            info.duration = Decimal(data['format'].get('duration', 0))
            info.bitrate = int(data['format'].get('bit_rate', 0))

        for stream in data.get('streams', []):
            if stream.get('codec_type') == 'video' and not info.video_codec:
                info.video_codec = stream.get('codec_name', '')
                info.width = stream.get('width', 0)
                info.height = stream.get('height', 0)
                info.pixel_format = stream.get('pix_fmt', '')
                info.color_transfer = stream.get('color_transfer', '')
                info.color_primaries = stream.get('color_primaries', '')

                fps_str = stream.get('r_frame_rate', '0/1')
                if '/' in fps_str:
                    num, den = fps_str.split('/')
                    info.fps = (
                        Decimal(num) / Decimal(den) if Decimal(den) > 0 else Decimal(0)
                    )

                pix_fmt = info.pixel_format.lower()
                info.is_10bit = any(
                    x in pix_fmt for x in ['10le', '10be', 'p010', 'yuv420p10']
                )

                hdr_transfers = ['smpte2084', 'arib-std-b67', 'bt2020-10', 'bt2020-12']
                info.is_hdr = (
                    info.color_transfer.lower() in hdr_transfers
                    or info.color_primaries.lower() == 'bt2020'
                    or (
                        info.is_10bit
                        and info.video_codec.lower() in ['hevc', 'h265', 'av1', 'vp9']
                    )
                )

                info.has_bframes = stream.get('has_b_frames', 0) > 0

            elif stream.get('codec_type') == 'audio' and not info.audio_codec:
                info.audio_codec = stream.get('codec_name', '')
                info.audio_channels = stream.get('channels', 2)
                info.audio_sample_rate = int(stream.get('sample_rate', 48000))

        return info
