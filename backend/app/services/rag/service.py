# services/rag/service.py — RAG pipeline orchestrator
#
# Responsibility: wire the full RAG pipeline into a single callable.
# Callers (e.g. function handlers) only need to call retrieve_anodiam_knowledge()
# and get back a grounded text answer — they don't need to know about the
# retriever, reranker, or synthesizer individually.
#
# Pipeline flow:
#   query + domain
#       → retriever.retrieve()     (embed query, cosine search, top-20 chunks)
#       → reranker.rerank()        (score chunks with Gemini Flash Lite, top-5)
#       → synthesizer.synthesize() (ground answer in top-5 chunks)
#       → str (plain text answer)

import asyncpg

from app.services.rag.retriever import retrieve
from app.services.rag.reranker import rerank
from app.services.rag.synthesizer import synthesize


async def retrieve_anodiam_knowledge(
    pool: asyncpg.Pool,
    query: str,
    domain: str | None = None,
) -> str:
    """
    Full RAG pipeline: retrieve → rerank → synthesize.

    Args:
        pool:   asyncpg connection pool (from app.state.pool)
        query:  the topic or question Syan needs grounded information on
        domain: knowledge domain to search — 'research', 'wisdom', or 'soul_score'
                Pass None to search across all domains (not recommended — noisy)

    Returns:
        Plain text answer grounded in the knowledge base.
        Returns a fallback string if no relevant chunks found.
    """
    # Step 1: Vector similarity search — returns top-20 candidate chunks
    chunks = await retrieve(pool=pool, query=query, domain=domain)

    if not chunks:
        # No chunks found — domain may be empty or query too niche
        return (
            "I don't have relevant information in my knowledge base for that topic."
        )

    # Step 2: Rerank — Gemini Flash Lite scores each chunk, returns top-5
    reranked = await rerank(query=query, chunks=chunks)

    # Step 3: Synthesize — Gemini Flash Lite generates a grounded answer
    answer = await synthesize(query=query, chunks=reranked)

    return answer