from fastapi import APIRouter, HTTPException
from ..transcoders.video import sessions, close_session

router = APIRouter()

@router.get('/close-session/{session}', status_code=204)
async def get_close_session(session: str):    
    if session not in sessions:
        raise HTTPException(404, 'Unknown session')
    close_session(session)