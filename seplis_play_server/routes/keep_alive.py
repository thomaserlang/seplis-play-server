import asyncio
from fastapi import APIRouter, HTTPException
from .. import transcoders
from seplis_play_server import config

router = APIRouter()

@router.get('/keep-alive/{session}', status_code=204)
async def keep_alive(session: str):
    if session not in transcoders.video.sessions:
        raise HTTPException(404, 'Unknown session')

    loop = asyncio.get_running_loop()
    transcoders.video.sessions[session].call_later.cancel()
    transcoders.video.sessions[session].call_later = loop.call_later(
        config.session_timeout,
        transcoders.video.close_session_callback,
        session
    )