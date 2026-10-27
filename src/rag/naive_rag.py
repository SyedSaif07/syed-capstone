"""Naive RAG for the capstone — W6.

Pure functions. Same pattern as the W6 demo notebook.
No frameworks (LangChain / LlamaIndex land in W11).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from openai import OpenAI

from src.pipeline.settings import Settings

EMBED_MODEL = "text-embedding-3-small"
CHAT_MODEL = "gpt-4o-mini"

_client = None


def _openai() -> OpenAI:
    """Lazy-init OpenAI client so imports don't require the key."""
    global _client
    if _client is None:
        _client = OpenAI()
    return _client


# ─── Chunking ────────────────────────────────────────────────────────

def chunk_text(text: str, size: int = 500, overlap: int = 50) -> list[str]:
    """Sliding window over characters."""
    if len(text) <= size:
        return [text]
    chunks = []
    i = 0
    while i < len(text):
        end = min(i + size, len(text))
        chunks.append(text[i:end])
        if end == len(text):
            break
        i = end - overlap
    return chunks


# ─── Corpus loading + indexing ───────────────────────────────────────

def load_corpus(corpus_dir: Path) -> list[dict]:
    """Load every .md and .txt file from corpus_dir, chunk each, return
    a flat list of {chunk_id, source_id, text}."""
    all_chunks = []
    for path in sorted(corpus_dir.glob("*")):
        if path.suffix.lower() not in {".md", ".txt"}:
            continue
        text = path.read_text(encoding="utf-8")
        for idx, chunk in enumerate(chunk_text(text)):
            all_chunks.append({
                "chunk_id": f"{path.stem}#{idx}",
                "source_id": path.stem,
                "text": chunk,
            })
    return all_chunks


def embed_batch(texts: list[str]) -> list[list[float]]:
    """One API call, list of vectors back."""
    resp = _openai().embeddings.create(model=EMBED_MODEL, input=texts)
    return [item.embedding for item in resp.data]


def build_index(chunks: list[dict]) -> list[dict]:
    """Attach a 'vector' field to each chunk. Returns the same list."""
    texts = [c["text"] for c in chunks]
    # Batch in groups of 100 to stay under API limits
    for i in range(0, len(texts), 100):
        batch = texts[i:i + 100]
        vectors = embed_batch(batch)
        for chunk, vec in zip(chunks[i:i + 100], vectors):
            chunk["vector"] = vec
    return chunks


def save_index(index: list[dict], path: Path) -> None:
    """Persist the indexed chunks to JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(index, ensure_ascii=False))


def load_index(path: Path) -> list[dict]:
    """Load a previously saved index."""
    return json.loads(path.read_text(encoding="utf-8"))


# ─── Retrieval + generation ──────────────────────────────────────────

def cosine(a: list[float], b: list[float]) -> float:
    va, vb = np.array(a), np.array(b)
    return float(np.dot(va, vb) / (np.linalg.norm(va) * np.linalg.norm(vb)))


def retrieve(query: str, index: list[dict], k: int = 3) -> list[dict]:
    q_vec = embed_batch([query])[0]
    scored = [(cosine(q_vec, c["vector"]), c) for c in index]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [{**c, "score": s} for s, c in scored[:k]]


SYSTEM = (
    "You are a helpful assistant. Answer the user's question using ONLY the "
    "provided context. If the context does not contain the answer, say so "
    "plainly. Cite the source id in square brackets after any fact you use."
)


def ask_rag(question: str, index: list[dict], settings: Settings,
            k: int = 3) -> dict[str, Any]:
    """Full naive RAG: retrieve → prompt → generate. Returns dict."""
    retrieved = retrieve(question, index, k=k)
    context = "\n\n".join(
        f"[{hit['chunk_id']}]\n{hit['text']}"
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
        "sources": [hit["chunk_id"] for hit in retrieved],
        "tokens_in": resp.usage.prompt_tokens,
        "tokens_out": resp.usage.completion_tokens,
    }
