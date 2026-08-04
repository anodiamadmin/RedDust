# api/chat.py — HTTP layer for the chat endpoint
# This file ONLY handles HTTP concerns: routing, session ID generation, and error mapping.
# No business logic lives here — all processing is delegated to the service layer (llm.py).
# This separation makes the business logic independently testable without HTTP context.

from uuid import uuid4

from fastapi import APIRouter, HTTPException

from app.schemas import ChatRequest, ChatResponse
from app.services.llm import call_gemini_safe

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    # If the client didn't provide a session_id, generate a new unique one.
    # The frontend is responsible for storing and echoing back this session_id in future requests.
    session_id = request.session_id or str(uuid4())

    # call_gemini_safe never raises — fallback response is returned on any failure
    return await call_gemini_safe(request.user_message, session_id)
