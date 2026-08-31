# services/function_dispatcher.py — Gemini Live function call router
#
# Responsibility: intercept function calls emitted by Gemini Live during an audio
# session, route them to the correct handler, and return a FunctionResponse back
# into the Gemini Live session so it can continue generating audio.
#
# Why a dispatcher instead of inline if/else in the audio relay loop?
#   - Clean separation — the audio relay loop should only care about audio bytes
#     and transcript segments, not business logic
#   - New function handlers can be added here without touching audio_relay.py
#   - Easier to test handlers in isolation
#
# How Gemini Live function calls work:
#   - During a session, Gemini may emit a ToolCall event containing one or more
#     FunctionCall objects (name + args dict)
#   - We must respond with a ToolResponse containing a FunctionResponse for each
#     FunctionCall before Gemini continues generating
#   - If we don't respond, the session stalls
#
# Registered functions (must match the tool declarations sent to Gemini Live):
#   - fetch_user_context(user_id)         → Step 15
#   - get_music_recommendation(mood_hint) → Step 16
#   - retrieve_anodiam_knowledge(query, domain) → Step 17

import asyncpg
from google.genai.types import FunctionResponse

# Import individual handlers — each handler owns one function's logic
from app.services.functions.user_context import handle_fetch_user_context
from app.services.functions.music import handle_get_music_recommendation
from app.services.functions.knowledge import handle_retrieve_anodiam_knowledge

from uuid import UUID


async def dispatch(
    function_name: str,
    function_args: dict,
    pool: asyncpg.Pool,
    user_id: UUID,
    session_id: UUID,
    conversation_id: UUID,
    turn_id: int,
) -> FunctionResponse:
    """
    Route a Gemini Live function call to the correct handler and return a
    FunctionResponse to send back into the session.

    Args:
        function_name: name of the function Gemini called (e.g. "fetch_user_context")
        function_args: dict of arguments Gemini passed to the function
        pool:          asyncpg connection pool for handlers that need DB access

    Returns:
        FunctionResponse — wraps the handler's result in the format Gemini Live expects.
        On unknown function name, returns an error FunctionResponse so the session
        doesn't stall waiting for a response that never comes.
    """
    if function_name == "fetch_user_context":
        result = await handle_fetch_user_context(
            pool=pool,
            user_id=user_id,
        )

    elif function_name == "get_music_recommendation":
        result = await handle_get_music_recommendation(
            args=function_args,
            user_id=user_id,
            session_id=session_id,
            conversation_id=conversation_id,
            turn_id=turn_id,
            pool=pool,
        )

    elif function_name == "retrieve_anodiam_knowledge":
        result = await handle_retrieve_anodiam_knowledge(
            pool=pool,
            query=function_args["query"],
            domain=function_args.get("domain"),
        )

    else:
        # Unknown function — return an error payload so Gemini can handle gracefully
        # rather than hanging the session waiting for a response
        result = {"error": f"Unknown function: {function_name}"}

    return FunctionResponse(name=function_name, response=result)