# test_rag_e2e.py — End-to-end RAG pipeline test (run once manually)
#
# What this does:
#   1. Connects to Supabase via asyncpg
#   2. Ingests ScientificResearchKnowledgeBase.docx (domain: "research")
#      and TraditionalWisdom.docx (domain: "wisdom")
#   3. Runs a test query through the full pipeline: retrieve → rerank → synthesize
#   4. Prints the answer
#
# Run from backend/ directory:
#   python test_rag_e2e.py
#
# This is NOT a pytest test — it makes real API calls and DB writes.
# Delete or gitignore after Step 8 is verified.

import asyncio
import asyncpg
from pathlib import Path

from app.config import settings
from app.services.rag.parsers import parse_scientific_research, parse_traditional_wisdom
from app.services.rag.embedder import embed_and_upsert
from app.services.rag.service import retrieve_anodiam_knowledge

# Absolute path to the RAG docs folder
DOCS_DIR = Path(__file__).parent.parent / "Docs" / "RAG_Docs"

# Test queries — one per domain to verify both are searchable
TEST_QUERIES = [
    ("What does research say about stress and wellbeing?", "research"),
    ("What does traditional wisdom say about emotional balance?", "wisdom"),
]


async def main():
    print("Connecting to Supabase...")
    pool = await asyncpg.create_pool(settings.SUPABASE_DB_URL, ssl="require")
    print("Connected.\n")

    # ── Step 1: Ingest docs ──────────────────────────────────────────────────

    research_path = DOCS_DIR / "ScientificResearchKnowledgeBase.docx"
    wisdom_path   = DOCS_DIR / "TraditionalWisdom.docx"

    print(f"Parsing {research_path.name}...")
    research_chunks = parse_scientific_research(str(research_path))
    print(f"  → {len(research_chunks)} chunks")

    print(f"Parsing {wisdom_path.name}...")
    wisdom_chunks = parse_traditional_wisdom(str(wisdom_path))
    print(f"  → {len(wisdom_chunks)} chunks\n")

    print("Embedding and upserting research chunks...")
    n = await embed_and_upsert(pool=pool, chunks=research_chunks, domain="research")
    print(f"  → {n} rows inserted (0 = all already existed, that's fine)\n")

    print("Embedding and upserting wisdom chunks...")
    n = await embed_and_upsert(pool=pool, chunks=wisdom_chunks, domain="wisdom")
    print(f"  → {n} rows inserted\n")

    # ── Step 2: Run test queries ─────────────────────────────────────────────

    for query, domain in TEST_QUERIES:
        print(f"Query [{domain}]: {query}")
        print("-" * 60)
        answer = await retrieve_anodiam_knowledge(pool=pool, query=query, domain=domain)
        print(answer)
        print("\n" + "=" * 60 + "\n")

    await pool.close()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())