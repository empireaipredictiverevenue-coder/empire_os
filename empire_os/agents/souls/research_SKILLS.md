# Research Agent — Skill Spec

Slim MindSearch (InternLM, arxiv 2407.20183) deep-research pattern for
Empire OS. Three stages, all free-tier safe.

## Stage 1 — Decompose (Planner, free OpenRouter)

Prompt the LLM to split a question into 3-5 parallel sub-queries.
Output contract: `{"subqueries": ["...", "..."]}`. Fallback: `[question]`.

## Stage 2 — Fan-out (parallel keyless search)

For each sub-query, POST to `https://lite.duckduckgo.com/lite/` with
`data={"q": query}`, `User-Agent: Mozilla/5.0 (compatible; EmpireOS/1.0)`,
timeout (4,8)s. Parse `result-link` / `result-snippet` rows. Cap 5 results
per query. Run threads concurrently (cap MAX_SUBQUERIES=5).

Keyless = no API key. Rate-limited; if DDG blocks, results may be empty —
solver says "sources thin". Optionally swap to Serply/Serper (keys in env)
later by editing `ddg_search`.

## Stage 3 — Solve (Solver, free OpenRouter)

Feed question + sub-queries + gathered snippets → LLM synthesizes a concise
answer with inline `[n]` citations mapping to the snippet list. Cite ONLY
from provided snippets. No invented sources.

## Artifact shape (written to /root/feedback/research_runs.jsonl)

```json
{"ts": 0.0, "engine": "research", "question": "...",
 "subqueries": ["...", "..."], "num_sources": 7,
 "answer": "cited synthesis with [1] [2] ...",
 "sources": [{"title": "...", "url": "..."}]}
```

- All content secret-scrubbed before write.
- If num_sources == 0, answer notes thin sources (honest, no hallucination).

## Consumption

- North-mini `growth_plan` / `agi_intel` can read `research_runs.jsonl` for
  grounded competitive/market research.
- Differs from last30days: that is recency/engagement aggregation; this is
  deep question answering with citations.
