"""Query rewriting for the capstone — Stretch lab W9.

Pick ONE pattern based on your golden-set failure analysis.
"""
from openai import OpenAI
from src.rag.retrieval import dense_search, rrf_fuse

_openai = None
def _get_openai():
    global _openai
    if _openai is None:
        _openai = OpenAI()
    return _openai


# ── HyDE — pick this OR one of the others below ──

def hyde_retrieve(query: str, k: int = 3) -> list[dict]:
    """LLM drafts a fake answer; embed and retrieve using that."""
    openai = _get_openai()
    resp = openai.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.3,
        messages=[{"role": "user", "content":
            f"Write a plausible one-paragraph answer to this question. Don't hedge.\n\n"
            f"Question: {query}\n\nHypothetical answer:"}],
    )
    hypothetical = resp.choices[0].message.content
    return dense_search(hypothetical, k=k)


# ── Multi-query — alternative ──

def multi_query_retrieve(query: str, k: int = 3, n_rewrites: int = 3) -> list[dict]:
    """LLM rewrites query N ways; retrieve for each; RRF-fuse the ranked lists."""
    openai = _get_openai()
    resp = openai.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.4,
        messages=[{"role": "user", "content":
            f"Rewrite this question {n_rewrites} ways that return the same answer. "
            f"One per line, no numbering.\n\nQuestion: {query}"}],
    )
    rewrites = [r.strip() for r in resp.choices[0].message.content.split("\n") if r.strip()]
    all_queries = [query] + rewrites[:n_rewrites]
    ranked_lists = [dense_search(q, k=5) for q in all_queries]
    return rrf_fuse(ranked_lists, k=60, top_n=k)


# ── Step-back — alternative ──

def step_back_retrieve(query: str, k: int = 3) -> list[dict]:
    """LLM generates a more general version; retrieve for both; fuse."""
    openai = _get_openai()
    resp = openai.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.2,
        messages=[{"role": "user", "content":
            f"Given a specific question, write a more general version that would "
            f"return the background needed to answer the specific question. Return only "
            f"the general question.\n\nSpecific: {query}\nGeneral:"}],
    )
    general = resp.choices[0].message.content.strip()
    ranked_lists = [dense_search(query, k=5), dense_search(general, k=5)]
    return rrf_fuse(ranked_lists, k=60, top_n=k)