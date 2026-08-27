# services/rag/embedder.py — Embedding pipeline
#
# Responsibility: take a list of text chunks (from parsers.py), embed them using
# Google's gemini-embedding-001, and upsert the results into the pgvector
# table `anodiam_knowledge` in PostgreSQL.
#
# Why gemini-embedding-001?
#   - 3072-dimensional output (highest quality embeddings from Google)
#   - Free tier available, production-ready
#   - Already in our google-genai dependency — no extra package needed
#
# Why upsert instead of insert?
#   - Allows re-ingesting the same file without creating duplicates
#   - Uses (filename, source, text) as a natural deduplication key via a unique index

import json
import uuid
import asyncpg
import math

import google.genai as genai
from app.config import settings
from app.services.rag.parsers import Chunk
from google.genai import types

# Google embedding API limit: max 100 texts per batch call
EMBEDDING_BATCH_SIZE = 100

# # Dimensionality of gemini-embedding-001 output — must match the vector column in DB
# max allowed by gemini-embedding-001 is 3072
EMBEDDING_DIM = 1536    # pending Rajanya's response #

# Initialise the Gemini client once at module load using the API key from config
client = genai.Client(api_key=settings.GEMINI_API_KEY)


def _batch(items: list, size: int) -> list[list]:
    """Split a list into sub-lists of at most `size` items each."""
    return [items[i : i + size] for i in range(0, len(items), size)]

# L2 normalization improves cosine similarity search accuracy.
def normalize_embedding(vector: list[float]) -> list[float]:
    """L2-normalize reduced-dimension Gemini embedding vectors for cosine search."""
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]

async def _embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embed a list of texts using gemini-embedding-001.
    Processes in batches to stay within the API's 100-text-per-call limit.
    Returns a flat list of embedding vectors in the same order as input texts.
    """
    all_embeddings: list[list[float]] = []

    for batch in _batch(texts, EMBEDDING_BATCH_SIZE):
        response = await client.aio.models.embed_content(
    		model="gemini-embedding-001",
    		contents=batch,
            config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM),
        )
        # Each response.embeddings entry corresponds to one input text
        all_embeddings.extend([normalize_embedding(e.values) for e in response.embeddings])

    return all_embeddings


async def embed_and_upsert(
    pool: asyncpg.Pool,
    chunks: list[Chunk],
    domain: str,
) -> int:
    """
    Main entry point for the embedding pipeline.

    Steps:
      1. Extract plain text from each chunk
      2. Embed all texts in batches via gemini-embedding-001
      3. Upsert each (text, embedding, metadata, domain) row into anodiam_knowledge
         — if a row with the same (filename, source, text) already exists, skip it
           (ON CONFLICT DO NOTHING) to avoid duplicates on re-ingestion

    Args:
        pool:   asyncpg connection pool (from app.state.pool)
        chunks: list of Chunk dicts produced by parse_xlsx() or parse_docx()
        domain: logical namespace for this knowledge base
                (e.g. "soul_score", "research", "wisdom")
                Used later to filter retrieval by topic area

    Returns:
        Number of rows actually inserted (not skipped by conflict)
    """
    if not chunks:
        return 0

    texts = [chunk["text"] for chunk in chunks]
    embeddings = await _embed_texts(texts)

    inserted = 0
    async with pool.acquire() as conn:
        for chunk, embedding in zip(chunks, embeddings):
            # Convert the Python list to a pgvector-compatible string format
            vector_str = "[" + ",".join(str(v) for v in embedding) + "]"

            result = await conn.execute(
                """
                INSERT INTO anodiam_knowledge (id, content, embedding, metadata, domain)
                VALUES ($1, $2, $3::vector, $4, $5)
                ON CONFLICT (domain, content_hash) DO NOTHING
                """,
                str(uuid.uuid4()),
                chunk["text"],
                vector_str,
                # Store metadata as valid JSON; asyncpg handles the jsonb cast
                json.dumps(chunk["metadata"]),
                domain,
            )
            # asyncpg returns "INSERT 0 1" or "INSERT 0 0" — parse the count
            if result.split()[-1] == "1":
                inserted += 1

    return inserted