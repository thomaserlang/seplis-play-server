import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from seplis_play.utils.sa_base_utils import SABase


class MExternalSubtitle(SABase):
    __tablename__ = 'external_subtitles'

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    path: Mapped[str] = mapped_column(sa.String(1000), nullable=False)
    type: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    language: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    forced: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default='0')
    default: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default='0')
    sdh: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default='0')
