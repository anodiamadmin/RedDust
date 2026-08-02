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


<<<<<<< Updated upstream
=======
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
# 4. MAIN FUNCTION
# ---------------------------------------------------------------------------

>>>>>>> Stashed changes
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
        model="gemini-2.0-flash",
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
