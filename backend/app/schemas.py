from typing import Optional
from pydantic import BaseModel


class ChatRequest(BaseModel):
    user_message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    followup_question: str
    session_id: str

class VoiceResponse(BaseModel):
    transcription: str
    reply: str
    followup_question: Optional[str] = None
    session_id: str