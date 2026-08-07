# services/rag/reranker.py — Reranking layer
#
# Responsibility: take the top-k chunks from the retriever and rerank them by
# relevance to the original query using Gemini Flash Lite.
#
# Why rerank after vector search?
#   - Vector similarity finds semantically close chunks but doesn't always rank
#     by true relevance to the specific query. A reranker fixes this.
#   - Example: "What is the soul score formula?" might retrieve chunks about
#     soul score history (high cosine similarity) but the formula chunk should
#     rank first. The reranker catches this.
#
# Why Gemini Flash Lite instead of a cross-encoder model?
#   - No heavy local dependency (avoids PyTorch/sentence-transformers ~1.5GB)
#   - Reranking operates on a small list (top 20 chunks) — API latency is acceptable
#   - Already in our dependency stack, no extra cost at this scale
#
# Scoring approach:
#   - For each chunk, ask Gemini Flash Lite: "On a scale of 0-10, how relevant
#     is this passage to the query?" — parse the integer score
#   - Sort chunks by score descending, return top_n

import asyncio
import google.genai as genai

from app.config import settings

# Final number of chunks to return after reranking
# Downstream synthesizer works best with 3-5 focused chunks
DEFAULT_TOP_N = 5

client = genai.Client(api_key=settings.GEMINI_API_KEY)


async def _score_chunk(query: str, chunk: dict) -> tuple[dict, float]:
    """
    Ask Gemini Flash Lite to score a single chunk's relevance to the query.
    Returns the chunk dict paired with its relevance score (0.0–10.0).

    The prompt is deliberately minimal to keep latency low — we just need a number.
    """
    prompt = (
        f"Query: {query}\n\n"
        f"Passage: {chunk['content']}\n\n"
        "On a scale of 0 to 10, how relevant is this passage to the query? "
        "Reply with a single integer only. No explanation."
    )

    response = await client.aio.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt,
    )

    try:
        score = float(response.text.strip())
    except ValueError:
        # If Gemini returns something unparseable, treat as 0 relevance
        score = 0.0

    return chunk, score


async def rerank(
    query: str,
    chunks: list[dict],
    top_n: int = DEFAULT_TOP_N,
) -> list[dict]:
    """
    Rerank retrieved chunks by relevance to the query using Gemini Flash Lite.

    Scores all chunks concurrently (asyncio.gather) to minimise latency —
    scoring sequentially would multiply the API round-trip time by len(chunks).

    Args:
        query:  the original user query
        chunks: list of chunk dicts from retriever.retrieve() (content, metadata, score)
        top_n:  number of top chunks to return after reranking

    Returns:
        List of top_n chunk dicts, sorted by reranker score descending.
        Each chunk gets a new key 'rerank_score' added.
    """
    # Score all chunks concurrently
    scored = await asyncio.gather(
        *[_score_chunk(query, chunk) for chunk in chunks]
    )

    # Sort by reranker score, highest first
    scored_sorted = sorted(scored, key=lambda x: x[1], reverse=True)

    # Attach rerank_score to each chunk for transparency/debugging
    result = []
    for chunk, score in scored_sorted[:top_n]:
        chunk["rerank_score"] = score
        result.append(chunk)

    return result