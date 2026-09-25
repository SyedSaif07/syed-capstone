"""W4 REFERENCE — src/pipeline/models.py

Final shape for W4: Answer additively gains confidence, sources, schema_version.
The W3 contract (content, cost_usd, retries) is unchanged — only new optional
fields with defaults, so any client written against W3 still works.
"""
from pydantic import BaseModel, Field


class Question(BaseModel):
    """Unchanged from W3."""
    question: str = Field(..., min_length=1)


class Answer(BaseModel):
    """W4 Answer — same W3 fields plus three new optional fields.

    Schema version is currently "v1". Stays v1 through any additive change
    (new optional fields, new endpoints, internal model swaps).
    Bumps to v2 only on breaking changes (field renamed, type changed, required
    field removed, semantic change).
    """
    # W3 fields — unchanged
    content: str
    cost_usd: float = 0.0001
    retries: int = 0

    # W4 additive fields — defaults make them backward-compatible
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    sources: list[str] = Field(default_factory=list)
    schema_version: str = "v1"
