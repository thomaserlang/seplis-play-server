import asyncio

import sqlalchemy as sa
from fastapi import APIRouter, Response
from pydantic import BaseModel

from seplis_play import database

router = APIRouter()


class HealthResponse(BaseModel):
    error: bool
    message: str
    service: str


@router.get('/health', name='Health check')
async def check_health_route(response: Response) -> list[HealthResponse]:
    result = await asyncio.gather(db_check())
    if any([r.error for r in result]):
        response.status_code = 500
    return list(result)


async def db_check() -> HealthResponse:
    r = HealthResponse(
        error=False,
        message='OK',
        service='Database',
    )
    try:
        async with database.session() as session:
            await session.execute(sa.text('SELECT 1'))
    except Exception as e:
        r.error = True
        r.message = f'Error: {str(e)}'
    return r
