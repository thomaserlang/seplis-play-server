import asyncio
import sqlalchemy as sa
from pydantic import BaseModel
from fastapi import APIRouter, Response
from seplis_play_server import database

router = APIRouter()

class Health_response(BaseModel):
    error: bool
    message: str
    service: str

@router.get('/health', response_model=list[Health_response])
async def check_health(response: Response):
    result = await asyncio.gather(
        db_check()
    )
    if any([r.error for r in result]):
        response.status_code = 500    
    return result

async def db_check() -> Health_response:
    r = Health_response(
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