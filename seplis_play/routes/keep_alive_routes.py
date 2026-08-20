from fastapi import APIRouter, HTTPException

from seplis_play.transcoding import base_transcoder

router = APIRouter()


@router.get('/keep-alive/{session}', status_code=204, name='Keep session alive')
async def keep_alive_route(session: str) -> None:
    if not await base_transcoder.refresh_session_timeout(session):
        raise HTTPException(404, 'Unknown session')
