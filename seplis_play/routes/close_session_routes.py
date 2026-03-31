from fastapi import APIRouter, HTTPException

from ..transcoding.base_transcoder import close_session, sessions

router = APIRouter()


@router.get('/close-session/{session}', status_code=204, name='Close session')
async def get_close_session_route(session: str) -> None:
    if session not in sessions:
        raise HTTPException(404, 'Unknown session')
    await close_session(session)
