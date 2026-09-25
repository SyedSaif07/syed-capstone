# Lab 4 — Model comparison: gpt-4o-mini vs gpt-4o

**Cohort member:** _<your name>_
**Date:** _<dd/mm/yyyy>_

## Numbers (filled in by `scripts/compare_models.py`)

```
Model            n    Total $     Avg $/q     Time
---------------------------------------------------
gpt-4o-mini     10    <fill in>   <fill in>   <fill in>s
gpt-4o          10    <fill in>   <fill in>   <fill in>s
```

> gpt-4o cost _<ratio>_ × more than gpt-4o-mini on the same questions.

## Two-paragraph eyeball reflection

### Paragraph 1 — where the gap mattered

_Write 4–6 sentences. For which of the 10 questions did the gpt-4o answer
feel meaningfully better than the gpt-4o-mini answer? Be specific — quote
short fragments if helpful. If you couldn't tell a difference for most
questions, say so._

### Paragraph 2 — your rough rule for when to reach for the bigger model

_Write 3–5 sentences. Based on what you saw, what kind of question would
make you switch to `gpt-4o`? What's the cost story you'd defend at Design
Review #1 if a stakeholder asked "why aren't you using the more capable
model for everything"?_

## Confidence calibration (optional)

The lab pipeline asks the model to return a `confidence` value in `[0, 1]`.
Skim the persisted rows in SQLite:

```bash
sqlite3 data/answers.db \
  "SELECT model, AVG(confidence), AVG(cost_usd) FROM answers GROUP BY model;"
```

Do the two models report similar confidence on the same questions, or do
they disagree on what they know? One sentence is enough.
