import json
import re
import asyncio
import logging
from typing import Optional

from google.genai import types
import google.genai as genai

from app.config import settings
from app.schemas import ChatResponse
from app.services.prompts import SYSTEM_PROMPT
from app.services.session_store import get_history, append_message

logger = logging.getLogger(__name__)

client = genai.Client(api_key=settings.GEMINI_API_KEY)

# ---------------------------------------------------------------------------
# 1. ROBUST RESPONSE PARSING
# ---------------------------------------------------------------------------

class ResponseParseError(Exception):
    """Raised when Gemini's response cannot be parsed into valid JSON."""
    pass


def _parse_response(text: Optional[str]) -> dict:
    """
    Extract JSON from Gemini's response with multiple fallback strategies.
    
    Handles:
      - Markdown fences (```json ... ```)
      - Plain JSON
      - JSON embedded inside explanatory text
      - Empty or None responses
    """
    if text is None or not text.strip():
        raise ResponseParseError("Gemini returned empty or None response")
    
    # Strategy 1: Strip markdown fences and try direct parse
    clean = re.sub(r"^```json\s*|^```\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        pass
    
    # Strategy 2: Extract first JSON object/array from text
    # Looks for {...} or [...] even if surrounded by fluff
    json_match = re.search(r'(\{.*\}|\[.*\])', clean, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    
    # Strategy 3: Try to find JSON between code blocks (middle of text)
    code_block_match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
    if code_block_match:
        try:
            return json.loads(code_block_match.group(1))
        except json.JSONDecodeError:
            pass
    
    logger.error(f"Failed to parse Gemini response. Raw text: {text[:500]}...")
    raise ResponseParseError(
        f"Could not extract valid JSON from response. Raw preview: {text[:200]}..."
    )


# ---------------------------------------------------------------------------
# 2. RETRY LOGIC WITH EXPONENTIAL BACKOFF
# ---------------------------------------------------------------------------

class GeminiAPIError(Exception):
    """Wraps all Gemini API failures for consistent handling upstream."""
    pass


MAX_RETRIES = 3
BASE_DELAY = 1.0  # seconds


async def _generate_with_retry(model, contents, config):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return await client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
            
        except Exception as e:
            error_msg = str(e).lower()
            
            # Retry on transient errors
            is_transient = any([
                "429" in error_msg,
                "503" in error_msg,
                "504" in error_msg,
                "timeout" in error_msg,
                "unavailable" in error_msg,
                "resource exhausted" in error_msg,
            ])
            
            if not is_transient or attempt == MAX_RETRIES:
                raise
            
            delay = BASE_DELAY * (2 ** (attempt - 1))
            logger.warning(f"Transient error (attempt {attempt}), retrying in {delay}s: {e}")
            await asyncio.sleep(delay)


# ---------------------------------------------------------------------------
# 3. ASYNC SESSION STORE INTERFACE
# ---------------------------------------------------------------------------

async def _get_history_async(session_id: str) -> list:
    """
    Wrap sync get_history in threadpool to avoid blocking the event loop.
    
    If your session store already has an async version (e.g., aioredis),
    replace this with the native async call.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, get_history, session_id)


async def _append_message_async(session_id: str, role: str, text: str) -> None:
    """Wrap sync append_message in threadpool for non-blocking I/O."""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, append_message, session_id, role, text)


# ---------------------------------------------------------------------------
# 4. MAIN FUNCTION — FULLY HARDENED
# ---------------------------------------------------------------------------

async def call_gemini(user_message: str, session_id: str) -> ChatResponse:
    """
    Async chat with Gemini featuring:
      - Conversation history
      - Retry with exponential backoff
      - Robust JSON parsing with multiple strategies
      - Non-blocking session persistence
      - Structured error handling
    """
    # Fetch history without blocking the event loop
    history = await _get_history_async(session_id)

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

    # Call Gemini with retry logic
    try:
        response = await _generate_with_retry(
            model=settings.GEMINI_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
            ),
        )
    except GeminiAPIError:
        raise  # Re-raise to let the API layer handle (return 503 to user, etc.)

    # Validate response has text before parsing
    if not hasattr(response, 'text') or response.text is None:
        # Check for safety blocks or finish reasons
        finish_reason = getattr(response.candidates[0], 'finish_reason', 'UNKNOWN') if response.candidates else 'NO_CANDIDATES'
        logger.error(f"Gemini returned no text. Finish reason: {finish_reason}")
        raise GeminiAPIError(f"AI response blocked or empty. Reason: {finish_reason}")

    # Parse with robust error handling
    try:
        data = _parse_response(response.text)
    except ResponseParseError as e:
        logger.error(f"Failed to parse response for session {session_id}: {e}")
        # Fallback: return raw text as reply, no followup
        data = {
            "reply": response.text[:1000],  # Truncate for safety
            "followup_question": None,
        }

    # Validate required fields exist
    if "reply" not in data:
        logger.error(f"Missing 'reply' field in parsed response: {data.keys()}")
        data["reply"] = "I apologize, but I couldn't generate a proper response."

    # Persist both turns asynchronously (non-blocking)
    await _append_message_async(session_id, "user", user_message)
    await _append_message_async(session_id, "model", response.text)

    return ChatResponse(
        reply=data["reply"],
        followup_question=data.get("followup_question"),
        session_id=session_id,
    )