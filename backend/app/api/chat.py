import json
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from app.schemas import ChatRequest, ChatResponse
from app.services.llm import call_gemini

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    session_id = request.session_id or str(uuid4())
    try:
        return await call_gemini(request.user_message, session_id)
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="LLM returned malformed JSON.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
