# services/rag/synthesizer.py — RAG response synthesis
#
# Responsibility: take the reranked chunks and the original query, then use
# Gemini 3.5 Flash Lite to synthesize a grounded, conversational answer.
#
# Why a separate synthesizer instead of doing this in the function handler?
#   - Single responsibility — the synthesizer only knows about "chunks + query → answer"
#   - Easier to swap models or prompts without touching the function handler
#   - Keeps the RAG pipeline self-contained and testable in isolation
#
# Grounding principle:
#   - The prompt explicitly instructs Gemini to answer ONLY from the provided chunks.
#   - If the chunks don't contain the answer, it should say so rather than hallucinate.
#   - This is critical for RedDust — Syan should never fabricate soul score data
#     or wellness research that isn't in the knowledge base.
#
# Output format:
#   - Plain conversational text — no markdown, no bullet points.
#   - Syan speaks in a warm, grounded tone, so the synthesis should match that.

import google.genai as genai
from app.config import settings

client = genai.Client(api_key=settings.GEMINI_API_KEY)

# System instruction for the synthesizer — keeps Syan grounded in source material
_SYNTHESIS_SYSTEM_PROMPT = """
You are Syan, a warm and grounded AI wellness companion.
Answer the user's query using ONLY the context passages provided below.
Do not add information from outside the provided passages.
If the passages do not contain enough information to answer, say so honestly.
Speak in a warm, conversational tone. No bullet points or markdown.
""".strip()


async def synthesize(query: str, chunks: list[dict]) -> str:
    """
    Synthesize a grounded answer from reranked chunks using Gemini 3.5 Flash Lite.

    Args:
        query:  the original user query
        chunks: reranked list of chunk dicts (each has 'content' and 'metadata')

    Returns:
        A plain-text answer grounded in the provided chunks.
        Returns a fallback message if chunks list is empty.
    """
    if not chunks:
        return (
            "I don't have enough information in my knowledge base to answer that. "
            "Could you rephrase or ask something else?"
        )

    # Format chunks into a numbered context block for the prompt
    # Including metadata (source) helps Gemini attribute claims correctly
    context_block = "\n\n".join(
        f"[{i+1}] (Source: {chunk['metadata'].get('source', 'unknown')})\n{chunk['content']}"
        for i, chunk in enumerate(chunks)
    )

    prompt = (
        f"Context passages:\n{context_block}\n\n"
        f"User query: {query}\n\n"
        "Answer based only on the passages above:"
    )

    response = await client.aio.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt,
        config={"system_instruction": _SYNTHESIS_SYSTEM_PROMPT},
    )

    return response.text.strip()