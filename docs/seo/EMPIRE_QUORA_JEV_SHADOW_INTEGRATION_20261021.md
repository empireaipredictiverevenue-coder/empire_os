# EmpireOS SEO / Quora — Jev typed decision integration

21 October 2026 · **Production evidence first / OBSERVE / no external provider**

## Implemented within the existing SEO department
- Reuses `empire_os.typed_decision_provider.TypedDecisionRequest`, `jev_strategy.review_jev_use_case` and `typed_decision_readiness.review_task_readiness`, alongside the existing Search Intelligence Quora topic catalogue.
- New read-only `GET /v1/search/quora/jev-shadow/review` on the existing loopback-only `empire-search-intelligence-api.service`. No new database, model server, cron, web crawler or autonomous agent.
- Validated **56 typed decision requests** across six industries. It explicitly distinguishes topic themes from real Quora question-page evidence; all source topics still require original-page verification and human editorial review.
- Reports true Jev readiness blockers: **zero real labelled cases, zero provider outputs, zero shadow records, no calibration/fallback/drift evaluations**. The Jev model provider is **disabled** and no tokens are billed. Semantic topic hypothesis labels are from the existing deterministic classifier, *not Jev predictions*.
- Existing Quora desk gains a 'Jev readiness' evidence panel in source. The active Founder Console runs an **immutable release** and must be independently rebuilt, pinned, and explicitly approved before this frontend addition becomes live. Do not restart the Founder Console on the basis of API approval or prior scoped permission.
- Dental and legal queues retain higher-risk specialist editorial review. No supplier/buyer routing, live posting, medical/legal content advice, public access, funds, database writes or revenue recognition.

## Exact evidence and operational gates
1. Verify independently sourced original Quora question URLs and content through authorised access. Search engine snippets are *not* an authenticated origin-page receipt.
2. An expert reviews genuine question intent and produces real **human-labelled** SEO tasks; keep originals, evidence references, timestamps and rights. Minimum 100 real labels in the existing readiness contract before offline evaluation; no synthetic cases counted.
3. Compare the deterministic semantic-intent baseline with optional Jev offline predictions on a held-out labelled set, with accuracy, error distribution, confidence calibration, latency, cost and failures measured. Current source has no activated external Jev provider.
4. Perform gated **zero-side-effect shadow evaluation**; independently review performance, fallbacks, drift, schema failures and source data rights.
5. Only after a separately scoped Founder approval may a provider be connected for review-only use. Typed decisions never authorise automated Quora posting, changed Search Fabric rankings, affiliate links, live buyer calls or revenue.

## Probes
```bash
cd /srv/empire_os
.venv/bin/python -B -m pytest -q tests/search_intelligence/test_jev_shadow_review_20261021.py
curl -sS http://127.0.0.1:8771/v1/search/quora/jev-shadow/review
```

The JSON response is not model inference or source verification. Do not represent `reviewed_topics_count` as labelled training cases, actual questions, commercial demand or indexed visitors.
