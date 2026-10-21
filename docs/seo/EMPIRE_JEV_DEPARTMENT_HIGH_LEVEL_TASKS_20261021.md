# EmpireOS SEO Director — Jev high-level departmental decision lanes
2026-10-21 | Read-only task contracts on existing Search Intelligence / marketing_growth.

## Delivered, not a new agent
A bounded `GET /v1/search/jev/department/review` consumes the **already exposed** read-only Search Intelligence department snapshot and the verified 56-theme Quora catalogue. No new scraper, cron, database, search engine or third-party model key is required. Existing source owners remain responsible for measurements and approved actions.

All 14 lanes carry Jev-oriented typed questions — Choice (which review queue), Score (review priority), and Noul (needs human) — plus the deterministic source controls. This release deliberately **does not call Jev or generate task scores**. The model cannot infer independent page rankings, editorial approvals, buyer revenue or commercial value from an aggregate.

## Tasks and original owning systems

| Department decision | Existing owner/source | Why useful |
|---|---|---|
| SEO portfolio allocation | marketing_growth | Review nine existing campaigns rather than adding competing ones |
| GSC legacy 404 recovery | search_intelligence.indexation | Triage already observed missing pages, no automatic redirects |
| Search Fabric freshness | search_fabric | Review stale/provider-cache faults before using SERP claims |
| Original content quality | semantic_opportunity_review | Prioritise two observed content-review candidates |
| GSC performance evidence | search_console | Choose useful page-level follow-up, don't invent rank positions |
| AEO citation verification | ai_visibility | Identify missing independent citation observations |
| GEO entity-reference coverage | ai_visibility | Verify mentions/source citations before claims |
| Competitor SERP position | rank_history | Independent rank observations required |
| Content decay refresh | content_decay | Needs comparable longitudinal URL-level evidence |
| Internal linking graph | internal_links | Requires actual crawl-level link graph |
| Technical SEO / structured data | technical_audit | Requires fresh issue receipts and human change review |
| USA/UK multisector expansion | marketing_growth | Compare source-ready markets, not assumed lead value |
| Quora editorial operations | quora_intelligence | Verify original questions, answer usefully and disclose affiliation |
| Organic revenue attribution | attribution | Trace opted-in enquiries → buyer acceptance → settled revenue |

## Live evidence at implementation (sample-scoped, not total sitewide)
- GSC final page sample **7–19 Oct**: 32 page rows; 64 impressions, zero clicks.
- In the returned page sample: **30 legacy missing-page entries**, 44 impressions, zero clicks; existing categories split 15 core-topic review and 15 off-core evidence hold.
- Existing semantic audit: two editorial-review candidates across four inspected public pages.
- Search Fabric cache: 1,896 entries, 1,801 stale, 91 fresh, four invalid.
- Independent ranking evidence, AEO citations, GEO mentions, actual buyer enquiry and realised revenue: still unverified.

These observations trigger **five aggregate-review lanes** only. **No lane is independently case-labelled or Jev model-ready.** No paid traffic, external model requests, database writes, publication, revenue recognition or outreach.

## Permission and rollout boundaries
- Backend deployment: Existing private Search Intelligence loopback API, preserve `/health`, summary, department and Quora responses.
- Frontend source: existing `/department/quora` workbench shows two groups, “Observed evidence to investigate” and “Held for original evidence.” The running Founder Console comes from an immutable Research-compatible release; **do not overwrite or restart it without a new staged candidate and specifically scoped approval**.
- Before inference: obtain original GSC query-page, SERP, citation, crawl and original Quora question observations as applicable, with rights and timestamps; collect real human labels, review against existing deterministic baselines and use `typed_decision_readiness` for promotion gates. Credentials and financial permissions remain separate.

## Verification
```bash
cd /srv/empire_os
.venv/bin/python -B -m pytest -q tests/search_intelligence/test_jev_department_review_20261021.py
curl --fail http://127.0.0.1:8771/v1/search/jev/department/review
```

The response's Choice/Score/Noul keys are typed **questions**, not answers or predicted scores. No supplier affiliation, rank movement, AEO mention, ROI or payout is inferred from them.
