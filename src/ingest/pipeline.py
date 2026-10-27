"""End-to-end ingestion pipeline for the capstone corpus.

Reads files from data/corpus/, parses by extension, chunks with
structure-aware strategy when possible, scrubs PII, enriches with the
9-field metadata schema, embeds, and upserts to Qdrant.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import pymupdf
from bs4 import BeautifulSoup
from docx import Document
from openai import OpenAI
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

from src.rag.qdrant_store import _get_client, ensure_collection, upsert_chunks

# Lazy-init the heavy things (analyzer takes ~5s to build)
_analyzer = None
_anonymizer = None
_openai = None


def _get_analyzer():
    global _analyzer
    if _analyzer is None:
        _analyzer = AnalyzerEngine()
    return _analyzer


def _get_anonymizer():
    global _anonymizer
    if _anonymizer is None:
        _anonymizer = AnonymizerEngine()
    return _anonymizer


def _get_openai():
    global _openai
    if _openai is None:
        _openai = OpenAI()
    return _openai


# ─── Step 1: parse ────────────────────────────────────────────────────

def parse_document(path: Path) -> str:
    """Dispatch to the right parser by file extension."""
    ext = path.suffix.lower()
    if ext == ".pdf":
        doc = pymupdf.open(str(path))
        text = "\n\n".join(page.get_text() for page in doc)
        doc.close()
        return text
    elif ext in (".html", ".htm"):
        soup = BeautifulSoup(path.read_text(), "html.parser")
        for tag in soup(["nav", "footer", "script", "style"]):
            tag.decompose()
        main = soup.find("main") or soup.find("body") or soup
        return main.get_text(separator="\n", strip=True)
    elif ext == ".docx":
        doc = Document(str(path))
        return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
    elif ext == ".md" or ext == ".txt":
        return path.read_text()
    else:
        raise ValueError(f"Unsupported file type: {ext}")


# ─── Step 2: chunk ────────────────────────────────────────────────────

def chunk_document(text: str, max_size: int = 400) -> list[str]:
    """Recursive chunker — paragraphs first, sentences if too long."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    for para in paragraphs:
        if len(para) <= max_size:
            chunks.append(para)
        else:
            sentences = re.split(r'(?<=[.!?])\s+', para)
            current = ""
            for sent in sentences:
                if len(current) + len(sent) + 1 <= max_size:
                    current = (current + " " + sent).strip()
                else:
                    if current:
                        chunks.append(current)
                    current = sent
            if current:
                chunks.append(current)
    return chunks


# ─── Step 3: scrub PII ────────────────────────────────────────────────

PII_PATTERNS = {
    "EMAIL": re.compile(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b'),
    "PHONE": re.compile(r'\+?\d{0,2}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3,4}(?:[-.\s]?\d{4})?\b'),
    "EMP_ID": re.compile(r'\bEMP-\d{4,6}\b'),
}


def scrub_pii(text: str) -> tuple[str, list[dict]]:
    """Regex + Presidio hybrid scrubber. Returns (clean_text, flags)."""
    flags = []
    scrubbed = text

    # Leg 1: regex
    for label, pattern in PII_PATTERNS.items():
        for match in pattern.findall(scrubbed):
            flags.append({"source": "regex", "type": label, "matched": match})
            scrubbed = scrubbed.replace(match, f"[{label}]")

    # Leg 2: Presidio
    analyzer = _get_analyzer()
    anonymizer = _get_anonymizer()
    results = analyzer.analyze(text=scrubbed, language="en")
    if results:
        anonymized = anonymizer.anonymize(text=scrubbed, analyzer_results=results)
        scrubbed = anonymized.text
        for r in results:
            flags.append({"source": "presidio", "type": r.entity_type,
                          "matched": text[r.start:r.end], "score": r.score})

    return scrubbed, flags


# ─── Step 4: enrich metadata ──────────────────────────────────────────

def enrich_metadata(text: str, path: Path, chunk_idx: int, pii_count: int) -> dict:
    """Build the 9-field metadata payload for one chunk."""
    return {
        "chunk_id": f"{path.stem}#{chunk_idx}",
        "source": path.name,
        "doc_type": path.suffix.lstrip(".").lower(),
        "section_path": path.stem,  # improve with structure-aware chunker later
        "page": None,  # improve for PDFs via per-page chunking
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),  # or from file metadata
        "language": "en",
        "version": "v1",
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "text": text,
        "pii_flags_count": pii_count,
    }


# ─── Step 5: ingest the whole corpus ──────────────────────────────────

def ingest_corpus(corpus_dir: Path, collection_name: str = "capstone_chunks_v2") -> dict:
    """Walk corpus_dir, ingest every supported file, upsert to Qdrant.

    Returns summary stats: n_files, n_chunks, n_pii_flags, per_file_breakdown.
    """
    store = type('Store', (), {})()
    store.client = _get_client()
    store.collection = collection_name
    ensure_collection(store)

    openai = _get_openai()

    all_chunks = []
    all_flags = []
    per_file = {}

    for path in sorted(corpus_dir.iterdir()):
        if path.suffix.lower() not in (".pdf", ".html", ".htm", ".docx", ".md", ".txt"):
            continue

        try:
            text = parse_document(path)
        except Exception as e:
            print(f"  ✗ FAILED to parse {path.name}: {e}")
            continue

        # Check for silent-failure trap (empty parse output)
        if len(text) < 50:
            print(f"  ⚠  {path.name}: only {len(text)} chars extracted — likely scanned/broken")
            continue

        chunk_texts = chunk_document(text, max_size=400)

        file_chunks = []
        for idx, chunk_text in enumerate(chunk_texts):
            scrubbed, flags = scrub_pii(chunk_text)
            chunk = enrich_metadata(scrubbed, path, idx, len(flags))
            file_chunks.append(chunk)
            all_flags.extend(flags)

        per_file[path.name] = {"chunks": len(file_chunks),
                               "pii_flags": sum(c["pii_flags_count"] for c in file_chunks)}
        all_chunks.extend(file_chunks)
        print(f"  ✓ {path.name}: {len(file_chunks)} chunks, "
              f"{sum(c['pii_flags_count'] for c in file_chunks)} PII flags")

    # Embed all chunks (batched for efficiency)
    print(f"\nEmbedding {len(all_chunks)} chunks...")
    texts = [c["text"] for c in all_chunks]
    # OpenAI accepts up to 2048 inputs per call; batch if needed
    vectors = []
    BATCH = 100
    for i in range(0, len(texts), BATCH):
        batch = texts[i:i + BATCH]
        resp = openai.embeddings.create(model="text-embedding-3-small", input=batch)
        vectors.extend([item.embedding for item in resp.data])

    # Upsert
    print(f"Upserting to Qdrant collection {collection_name!r}...")
    upsert_chunks(store, all_chunks, vectors)

    return {
        "n_files": len(per_file),
        "n_chunks": len(all_chunks),
        "n_pii_flags": len(all_flags),
        "per_file": per_file,
    }


if __name__ == "__main__":
    stats = ingest_corpus(Path("data/corpus"))
    print(f"\n══ Summary ══")
    print(f"Files ingested: {stats['n_files']}")
    print(f"Total chunks:   {stats['n_chunks']}")
    print(f"PII flags:      {stats['n_pii_flags']}")