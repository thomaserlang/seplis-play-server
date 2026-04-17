from fastapi import APIRouter, HTTPException

from ..transcoding.base_transcoder import (
    TranscodeDecision,
    sessions,
)

router = APIRouter()


@router.get(
    '/transcode-decision/{session}',
    name='Get transcode decision for session',
)
async def get_transcode_decision_route(session: str) -> TranscodeDecision:
    session_model = sessions.get(session)
    decision = session_model.transcode_decision if session_model else None
    if decision is None:
        raise HTTPException(404, 'Unknown session')
    return decision
