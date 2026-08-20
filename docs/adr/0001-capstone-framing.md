# ADR-0001: Capstone Framing — OWASP Top10 documentation
- **Status:** Draft v1
- **Date:** 2026-08-12
- **Author:** Syed Saifullah M
## Context
Application Security is a key factor to be considered and not to be neglected at any cost when building an application that runs at scale. This is targeted to create awareness among the developers community and impart application security knowledge amongst them.
## Decision — Solution Framing Canvas
| Box | Your answer |
|-----|-------------|
| **Inputs** | A question on OWASP 10. Eg: Give some example attack scenarios on broken access control + Document corpus  |
| **Outputs** | An anwser responding  to the user's question with references from the documentation. |
| **Tools** | gpt-4o-mini for generation, a
vector store like chroma db |
| **Memory** | we can implement persistent memory with sqlite or postgres |
| **Autonomy level** |This is a chatbot |
| **Decision boundaries** | It can answer within the scope of the documentation with proper references else It can say "I dont know" |
## Consequences
- **Positive:** <2–3 bullet points: what this design unlocks>
- **Negative / risks:** <2–3 bullet points: what's harder / costlier /
riskier because of this choice>
- **Things we'll re-visit:** <1–2 specific things we'll come back to in
later ADRs>