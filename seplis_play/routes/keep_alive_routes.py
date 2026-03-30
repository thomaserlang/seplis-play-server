import asyncio

from fastapi import APIRouter, HTTPException

from seplis_play import config
from seplis_play.transcoders import base_transcoder

router = APIRouter()


@router.get('/keep-alive/{session}', status_code=204, name='Keep session alive')
async def keep_alive_route(session: str) -> None:
    if session not in base_transcoder.sessions:
        raise HTTPException(404, 'Unknown session')

    loop = asyncio.get_running_loop()
    base_transcoder.sessions[session].call_later.cancel()
    base_transcoder.sessions[session].call_later = loop.call_later(
        config.session_timeout, base_transcoder.close_session_callback, session
    )
