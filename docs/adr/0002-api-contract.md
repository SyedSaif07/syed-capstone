# ADR 0002 — API contract for /ask and /ask_batched

**Status**: Accepted (W3) · Extended W4
**Date**: Week 3 (original) · Week 4 (versioning rule + cost budget added)

## Context

The cohort needs a stable HTTP surface that downstream consumers (UI, future
agents, evaluation harness, stakeholders running `curl`) can depend on while
the internals of the answer-generation pipeline evolve across W4, W6, W13,
W19, and beyond.

Without a written contract, each week's pipeline change risks silently
breaking a consumer.

## Decision

### Endpoints (locked W3)

- `POST /ask` — request: `{"question": "..."}`; response: `text/plain` stream
- `POST /ask_batched` — request: `{"question": "..."}`; response: `Answer` JSON
- `GET  /health` — response: `{"status": "ok"}`

### Pydantic shapes (W3, additively extended W4)

```
Question:
  question: str  (min_length=1)

Answer (W3 fields):
  content: str
  cost_usd: float
  retries: int

Answer (W4 additive fields):
  confidence: float = 1.0        # 0.0 to 1.0
  sources: list[str] = []
  schema_version: str = "v1"
```

W4 added the bottom three fields. The W3 fields are unchanged.

### Schema versioning rule (added W4)

Every `Answer` carries a `schema_version` field.

**Today's shape is `v1`.** It stays `v1` through any additive change:
new optional fields with defaults, new endpoints at different paths,
internal model swaps, prompt edits that don't change the output shape,
retry / logging / observability changes.

**Breaking changes ship as a new `schema_version`** (`v2`, `v3`, …):
removing a required field, renaming a public field, changing a field's
type, making an optional field required, semantic changes (e.g.,
`cost_usd` repurposed to mean something other than USD), changing the
error-response shape.

When `v2` ships:
- `/ask` and `/ask_batched` still return `v1` by default.
- A header `X-Schema-Version: v2` (or `?schema_version=v2`) opts the
  caller into the new shape.
- Both versions are supported in parallel for at least two weeks before
  `v1` is retired.
- The deprecation date is announced in the ADR before removal.

### Cost budget (added W4)

Capstone `/ask_batched` calls cost ≤ **$0.01 each** on average over a
representative batch of 10 questions. This is a soft budget — the
intent is to fail loud in observability if average cost suddenly
doubles, not to reject individual expensive calls.

The cohort confirms or refines this number against the actual results
of Lab Step 3 (`scripts/compare_models.py`).

### Chosen default model (added W4)

The default `Settings.model` is **`gpt-4o-mini`** for the lab. `gpt-4o`
is available via the same code path for harder questions or when the
mini model's confidence is low.

> Lab Step 4 — cohort fills in their own reasoning here, e.g.
> "I picked `gpt-4o-mini` because the comparison run showed it answers
> 8 of 10 questions correctly at $X total cost, which is well under
> the budget of $0.01/answer."

## Consequences

**Positive**
- Consumers can rely on `Answer.content`, `Answer.cost_usd`, and
  `Answer.retries` from W3 forwards.
- Internal refactors (W4 tool-calling, W6 retrieval, W13 tool-use,
  W19 agents) ship without consumer breakage.
- A clear bump policy means the cohort doesn't have to negotiate every
  schema change with downstream consumers.

**Negative**
- Supporting two `schema_version`s in parallel requires the API code
  to branch on the version header for at least two weeks per bump.
- The `cost_usd` budget assumes the cohort runs the comparison
  regularly enough to catch regressions.

## Notes

- JSON + Pydantic carries the cohort through the rest of the
  programme. Avro/Protobuf would enforce the same versioning
  discipline with more ceremony — not adopted for this cohort.
