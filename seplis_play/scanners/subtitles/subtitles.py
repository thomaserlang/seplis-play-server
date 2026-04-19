import iso639
import sqlalchemy as sa

from seplis_play import database
from seplis_play.schemas.source_schemas import SourceStream

from .subtitle_models import MExternalSubtitle


async def get_external_subtitles(filename: str) -> list[SourceStream]:
    result: list[SourceStream] = []
    async with database.session() as session:
        filename = filename.rsplit('.', 1)[0]
        subtitles = await session.scalars(
            sa.select(MExternalSubtitle).where(
                MExternalSubtitle.path.like(f'{filename}.%'),
            )
        )
        for r in subtitles:
            if not iso639.is_language(r.language):
                continue
            lang = iso639.Lang(r.language)
            title: str = lang.name
            if r.sdh:
                title += ' (SDH)'
            if r.forced:
                title += ' (Forced)'
            s = SourceStream(
                title=title,
                language=r.language,
                index=r.id + 1000,
                group_index=r.id + 1000,
                codec=r.type,
                default=r.default,
                forced=r.forced,
            )
            result.append(s)
    return result
