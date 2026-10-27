"""Qdrant-backed RAG for the capstone — W7 upgrade of W6's naive_rag.

Same public interface as W6's ask_rag: (question, store, k) → dict.
Storage layer swapped from JSON+numpy to Qdrant.
"""
from __future__ import annotations

from typing import Any

from openai import OpenAI

from src.pipeline.settings import Settings
from src.rag.qdrant_store import QdrantStore, load_store
from src.rag.retrieval import retrieve as retrieve_v9   # NEW


CHAT_MODEL = "gpt-4o-mini"
EMBED_MODEL = "text-embedding-3-small"

_client = None


def _openai() -> OpenAI:
    """Lazy-init the OpenAI client (unit tests can import without a key)."""
    global _client
    if _client is None:
        _client = OpenAI()
    return _client


def embed_query(text: str) -> list[float]:
    """Single-string embedding. Used at query time."""
    resp = _openai().embeddings.create(model=EMBED_MODEL, input=[text])
    return resp.data[0].embedding


def retrieve(store: QdrantStore, query: str, k: int = 3) -> list[dict[str, Any]]:
    """Embed the query, ask Qdrant for top-K, return list of hits."""
    q_vec = embed_query(query)
    results = store.client.query_points(
        collection_name=store.collection,
        query=q_vec,
        limit=k,
    ).points
    return [
        {
            "chunk_id": h.payload["chunk_id"],
            "source_id": h.payload["source_id"],
            "text": h.payload["text"],
            "score": h.score,
        }
        for h in results
    ]


SYSTEM = (
    "You are a helpful assistant. Answer the user's question using ONLY the "
    "provided context. If the context does not contain the answer, say so "
    "plainly. Cite the source_id in square brackets after any fact you use."
)


def ask_rag(question: str, store: QdrantStore | None = None,
            settings: Settings | None = None, k: int = 3) -> dict[str, Any]:
    """Full pipeline: embed → retrieve → prompt → generate. Returns dict."""
    if store is None:
        store = load_store()

    # retrieved = retrieve(store, question, k=k)
    retrieved = retrieve_v9(question, k=k)
    context = "\n\n".join(
        f"[{hit['chunk_id']}] (source: {hit['source_id']})\n{hit['text']}"
        for hit in retrieved
    )

    resp = _openai().chat.completions.create(
        model=CHAT_MODEL,
        temperature=0.0,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content":
                f"Context:\n{context}\n\n---\n\nQuestion: {question}"},
        ],
    )

    return {
        "answer": resp.choices[0].message.content,
        "sources": [h["source_id"] for h in retrieved],
        "chunk_ids": [h["chunk_id"] for h in retrieved],
        "tokens_in": resp.usage.prompt_tokens,
        "tokens_out": resp.usage.completion_tokens,
    }