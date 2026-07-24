# Implementation Plan: Free Audit Lead Magnet

**Branch**: `001-free-audit-lead-magnet` | **Date**: 2026-07-21 | **Spec**: /root/empire_os/.specify/specs/free-audit-lead-magnet/spec.md

## Summary

Build a free SEO audit lead magnet: POST `/v1/audit/free` runs claude-seo deterministic checks (fetch, parse, PSI, tech), returns 0-100 score + grade A-F + 3 fixes, generates branded PDF, emails via Resend, stores lead in `si_buyer_outreach` with niche/metro, triggers funnel_agent. Landing page at `/tools/audit/` rendered by cinematic_lp_agent. Target: 3 days to live.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: FastAPI (hub), claude-seo scripts (fetch_page, parse_html, pagespeed_check), WeasyPrint/Jinja2 (PDF), Resend (email), SQLite (empire_os.db)
**Storage**: SQLite (empire_os.db — si_buyer_outreach, si_funnel_event), filesystem (/tmp PDFs, /srv/aeo/tools/audit/ landing)
**Testing**: pytest, curl integration test
**Target Platform**: Linux (empire-hub container or new audit-api container on Vultr/Incus)
**Project Type**: Web service (FastAPI endpoint + static landing page)
**Performance Goals**: <10s response (async PDF), 5 req/min/IP rate limit
**Constraints**: 100 emails/day hard cap (Resend), PSI optional (API key in .env), no paid APIs without key

## Constitution Check

- Revenue loop before features ✓ (audit captures leads for $10 trial)
- Ship free audit in 3 days ✓
- Every script reusable from claude-seo ✓
- No paid API without key in .env ✓
- 100/day email cap hard limit ✓

## Project Structure

```
empire_os/
├── empire_os/
│   ├── audit_api.py          # Core audit engine (exists, needs completion)
│   ├── audit_report.py       # NEW: PDF generator (Jinja2 + WeasyPrint)
│   ├── hub.py                # ADD: /v1/audit/free endpoint
│   ├── mail_sender.py        # USE: send PDF via Resend
│   ├── funnel.py             # USE: auto-advance lead
│   └── agents/
│       └── cinematic_lp_agent.py  # USE: render landing page
├── tools/
│   └── audit/                # NEW: landing page source
│       └── index.html        # rendered by cinematic_lp_agent
├── feedback/
│   └── audit_log.jsonl       # audit events
└── .specify/
    └── specs/
        └── free-audit-lead-magnet/
            ├── spec.md       # done
            ├── plan.md       # this file
            ├── research.md   # Phase 0
            ├── data-model.md # Phase 1
            ├── quickstart.md # Phase 1
            ├── contracts/    # Phase 1
            └── tasks.md      # Phase 2
```

## Phase 0: Research (COMPLETE)

Key findings:
- claude-seo scripts import OK (fetch_page, parse_html, pagespeed_check)
- PSI needs API key (PAGESPEED_API_KEY in .env) — optional for free tier
- WeasyPrint needs system deps (pango, cairo) — install in container
- Resend domain unverified → use onboarding@resend.dev for testing
- 24 AEO niches exist at /srv/aeo/ — can map niche→metro for landing page

## Phase 1: Design

### Data Model

**si_buyer_outreach** (existing):
- id, email, niche, metro, source=free_audit, status=discovered, created_at, meta_json={score, grade, url}

**si_funnel_event** (existing):
- id, prospect_id, state=discovered→matched, created_at

**audit_log.jsonl** (new):
- {ts, email, url, niche, metro, score, grade, checks_summary}

### API Contract

```
POST /v1/audit/free
Request: {url: string, email: string, niche?: string, metro?: string, consent: boolean}
Response: {score: int, grade: "A-F", checks: {...}, pdf_url: string, audit_id: string}
Errors: 400 (validation), 429 (rate limit), 500 (internal)
```

### Quickstart

```bash
# 1. Install deps
pip install weasyprint jinja2  # in container

# 2. Run hub with new endpoint
cd /root/empire_os && python3 -m empire_os.hub

# 3. Test
curl -X POST http://localhost:8081/v1/audit/free \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com","email":"test@example.com","niche":"plumbing","metro":"NYC","consent":true}'

# 4. Render landing page
cd /root/empire_os && python3 -m empire_os.agents.cinematic_lp_agent \
  --brief '{"niche":"audit","headline":"Free 60-Second SEO Health Check","subhead":"Enter your URL. Get a score. Fix the leaks.","cta":"Start Free Audit","price":"$0"}'
```

## Phase 2: Tasks (tasks.md)

Will be generated after Phase 1 approval. Estimated 12-15 tasks across:
- audit_report.py (PDF generation)
- hub.py endpoint integration
- cinematic_lp_agent brief for landing page
- mail_sender integration
- funnel_agent trigger
- rate limiting
- tests + verification