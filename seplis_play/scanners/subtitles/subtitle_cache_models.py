import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from seplis_play.utils.sa_base_utils import SABase
from seplis_play.utils.sa_zstd_text_utils import ZstdText


class MCachedSubtitle(SABase):
    __tablename__ = 'cached_subtitles'

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    source_path: Mapped[str] = mapped_column(sa.String(400), nullable=False)
    stream_index: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    type: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    language: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    forced: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default='0')
    default: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default='0')
    content: Mapped[str | None] = mapped_column(ZstdText)
