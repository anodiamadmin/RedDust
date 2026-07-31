from uuid import uuid4

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Optional

from app.schemas import VoiceResponse
from app.services.voice import call_gemini_voice

router = APIRouter()


@router.post("/voice", response_model=VoiceResponse)
async def voice(
    audio: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
) -> VoiceResponse:
    session_id = session_id or str(uuid4())
    try:
        audio_bytes = await audio.read()
        mime_type = audio.content_type or "audio/m4a"
        return await call_gemini_voice(audio_bytes, mime_type, session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))