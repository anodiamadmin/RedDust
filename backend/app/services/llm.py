import json
import re

from google.genai import types
import google.genai as genai

from app.config import settings
from app.schemas import ChatResponse
from app.services.prompts import SYSTEM_PROMPT
from app.services.session_store import get_history, append_message

client = genai.Client(api_key=settings.GEMINI_API_KEY)


def _parse_response(text: str) -> dict:
    clean = re.sub(r"```json|```", "", text).strip()
    return json.loads(clean)


async def call_gemini(user_message: str, session_id: str) -> ChatResponse:
    history = get_history(session_id)

    # Build contents list from history + current message
    contents = []
    for msg in history:
        contents.append(
            types.Content(
                role=msg["role"],
                parts=[types.Part(text=msg["text"])],
            )
        )
    contents.append(
        types.Content(
            role="user",
            parts=[types.Part(text=user_message)],
        )
    )

    response = await client.aio.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
        ),
    )

    data = _parse_response(response.text)

    # Persist both turns
    append_message(session_id, "user", user_message)
    append_message(session_id, "model", response.text)

    return ChatResponse(
        reply=data["reply"],
        followup_question=data["followup_question"],
        session_id=session_id,
    )
