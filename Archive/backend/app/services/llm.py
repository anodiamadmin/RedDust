# services/llm.py — Core LLM integration layer
# Responsible for: building conversation context, calling Gemini asynchronously,
# parsing the structured JSON response, persisting the conversation, and
# delegating mood + track assembly to mood_recommendation.py.

import json
import re

import logging

from google.genai import types
import google.genai as genai

from app.config import settings
from app.schemas import ChatResponse
from app.services.prompts import SYSTEM_PROMPT
from app.services.session_store import get_history, append_message
from app.services.mood_recommendation import build_syan_response, detect_mood_from_keywords, recommend_tracks

# Initialise the Gemini client once at module load time using the API key from config
client = genai.Client(api_key=settings.GEMINI_API_KEY)


def _parse_response(text: str) -> dict:
    """
    Strips accidental markdown code fences (```json ... ```) that Gemini sometimes adds
    despite being told not to, then parses the cleaned string as JSON.
    Raises json.JSONDecodeError if the result is still not valid JSON.
    """
    clean = re.sub(r"```json|```", "", text).strip()
    return json.loads(clean)


async def call_gemini(user_message: str, session_id: str) -> ChatResponse:
    """
    Main function that orchestrates the full LLM request-response cycle.

    Steps:
    1. Fetch conversation history for this session from the in-memory store
    2. Build the `contents` list Gemini expects (prior turns + current message)
    3. Call Gemini asynchronously (async = server handles other requests while waiting)
    4. Parse the structured JSON response
    5. Persist both the user message and the model reply to session history
    6. Assemble and return the final ChatResponse via mood_recommendation
    """

    # Step 1: Load prior conversation turns for this session
    history = get_history(session_id)
    history_texts = [msg["text"] for msg in history]  # plain text list used for keyword fallback

    # Step 2: Build the multi-turn contents list
    # Gemini requires history in its own Content/Part format — not raw dicts
    contents = []
    for msg in history:
        contents.append(
            types.Content(
                role=msg["role"],           # "user" or "model"
                parts=[types.Part(text=msg["text"])],
            )
        )
    # Append the current user message at the end
    contents.append(
        types.Content(
            role="user",
            parts=[types.Part(text=user_message)],
        )
    )

    # Step 3: Call Gemini asynchronously
    # `client.aio` is the async variant — avoids blocking the event loop during the I/O wait
    response = await client.aio.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,   # Syan persona + JSON output contract
        ),
    )

    # Guard: Gemini occasionally returns empty responses on safety filter triggers
    if response.text is None:
        raise ValueError("LLM returned an empty response.")

    # Step 4: Parse the JSON Gemini was instructed to return
    data = _parse_response(response.text)

    # Step 5: Persist both turns so future messages have full conversation context
    append_message(session_id, "user", user_message)
    # Store reply + followup together as a single model turn (mirrors how the LLM sees it)
    append_message(session_id, "model", f"{data['reply']} {data['followup_question']}")

    # Step 6: Build and return the final structured response
    return build_syan_response(
        reply=data["reply"],
        followup_question=data["followup_question"],
        session_id=session_id,
        user_message=user_message,
        history=history_texts,
        detected_mood=data.get("detected_mood"),  # May be None if LLM skipped the field
    )

# hardcoded fallback response for when Gemini fails (network, parse error, empty response, API quota)
async def call_gemini_safe(user_message: str, session_id: str) -> ChatResponse:
    """
    Resilient wrapper around call_gemini.
    On any failure (network, parse error, empty response, API quota), returns a
    hardcoded fallback response so the app never surfaces a raw 500 to the user.
    Mood and tracks are still derived locally via keyword detection so the response
    remains somewhat contextual even without the LLM.
    """
    try:
        return await call_gemini(user_message, session_id)
    except Exception as e:
        logging.getLogger(__name__).error("call_gemini failed: %s", e, exc_info=True)
        fallback_mood = detect_mood_from_keywords(user_message)
        return ChatResponse(
            reply="I'm having a little trouble connecting right now. I'm still here though.",
            followup_question="How are you feeling at this moment?",
            session_id=session_id,
            detected_mood=fallback_mood,
            music_requested=False,
            tracks=recommend_tracks(fallback_mood),
        )
