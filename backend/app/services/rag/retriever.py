# services/rag/retriever.py — Vector similarity search
#
# Responsibility: given a query string, embed it and find the most semantically
# similar chunks in the anodiam_knowledge table using pgvector cosine similarity.
#
# Why cosine similarity?
#   - text-embedding-004 / gemini-embedding-001 vectors are not unit-normalized,
#     so cosine similarity (1 - cosine_distance) is more reliable than dot product.
#   - pgvector operator <=> = cosine distance (lower = more similar)
#
# Why filter by domain?
#   - The knowledge base stores content from multiple topic areas (e.g. "soul_score",
#     "research", "wisdom"). Filtering ensures the query only searches the relevant
#     subset, improving precision and reducing noise.

import asyncpg
import google.genai as genai

from app.config import settings
from app.services.rag.embedder import EMBEDDING_BATCH_SIZE

# Number of candidate chunks to retrieve before reranking
# Retrieve more than needed (e.g. 20) so the reranker has room to work
DEFAULT_TOP_K = 20

# Gemini client — reuses same API key as embedder
client = genai.Client(api_key=settings.GEMINI_API_KEY)


async def embed_query(query: str) -> list[float]:
    """
    Embed a single query string using gemini-embedding-001.
    Kept separate from embedder.py's batch embed because queries are
    always single strings — no batching needed.
    """
    response = await client.aio.models.embed_content(
        model="gemini-embedding-001",
        contents=[query],
    )
    return response.embeddings[0].values


async def retrieve(
    pool: asyncpg.Pool,
    query: str,
    domain: str,
    top_k: int = DEFAULT_TOP_K,
) -> list[dict]:
    """
    Embed the query and run a cosine similarity search against anodiam_knowledge.

    Args:
        pool:   asyncpg connection pool from app.state.pool
        query:  the user's natural language query
        domain: knowledge domain to search within (e.g. "soul_score", "research")
        top_k:  number of top results to return (before reranking)

    Returns:
        List of dicts with keys: content, metadata, score
        Ordered by similarity (most similar first).
    """
    query_embedding = await embed_query(query)

    # Convert Python list to pgvector-compatible string format
    vector_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                content,
                metadata,
                -- cosine distance: lower = more similar, so we invert for a score
                1 - (embedding <=> $1::vector) AS score
            FROM anodiam_knowledge
            WHERE domain = $2
            ORDER BY embedding <=> $1::vector
            LIMIT $3
            """,
            vector_str,
            domain,
            top_k,
        )

    return [
        {
            "content": row["content"],
            "metadata": row["metadata"],
            "score": row["score"],
        }
        for row in rows
    ]