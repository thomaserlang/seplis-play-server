from dataclasses import dataclass
from decimal import Decimal


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
