# services/functions/knowledge.py — Handler for retrieve_anodiam_knowledge()
#
# Responsibility: handle the Gemini Live function call "retrieve_anodiam_knowledge"
# by calling the RAG pipeline and returning the result as a dict.
#
# Why a separate handler instead of calling service.py directly from the dispatcher?
#   - The dispatcher only deals with routing — it shouldn't know RAG internals
#   - The handler owns the interface contract: what args come in, what dict goes out
#   - FunctionResponse wrapping happens in the dispatcher, not here — clean separation
#
# Return format:
#   {"answer": str} — Gemini Live receives this as the function result and uses
#   it to continue generating its audio response to the user

import asyncpg

from app.services.rag.service import retrieve_anodiam_knowledge


async def handle_retrieve_anodiam_knowledge(
    pool: asyncpg.Pool,
    query: str,
    domain: str | None = None,
) -> dict:
    """
    Handle the retrieve_anodiam_knowledge function call from Gemini Live.

    Args:
        pool:   asyncpg connection pool (passed through from dispatcher)
        query:  the topic Syan needs grounded knowledge on
        domain: knowledge domain — 'research', 'wisdom', or 'soul_score'

    Returns:
        Dict with key 'answer' containing the grounded text response.
        Gemini Live receives this dict as the FunctionResponse payload.
    """
    answer = await retrieve_anodiam_knowledge(
        pool=pool,
        query=query,
        domain=domain,
    )

    return {"answer": answer}