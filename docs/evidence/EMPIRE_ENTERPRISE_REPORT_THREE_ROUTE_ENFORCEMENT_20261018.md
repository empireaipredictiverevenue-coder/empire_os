# Empire AI — existing enterprise report route evidence enforcement

**18 October 2026 | Source-evidence discipline | Canonical repository /srv/empire_os**

## Before this change

- Existing Founder read API runs through **systemd `empire-founder-dashboard-api.service`**, loopback TCP `127.0.0.1:8766`.
- Existing router `empire_os/predictive_revenue_demo_api.py` was **tracked but dirty with 55 insertions belonging to another agent**. The JSON, HTML, and Markdown enterprise-report paths appeared only in those uncommitted edits; original tracked HEAD contained two demo routes and no enterprise-report paths.
- The report builder `empire_os/predictive_revenue_enterprise_report.py` and renderer `empire_os/predictive_revenue_report_presentation.py` were untracked work owned by another agent. The guard `empire_os/enterprise_report_claim_guard.py` was committed in `eb1583d8`.
- A copied report with `completeness.findings_verified=42` previously rendered false verified text in the original Markdown path, even when no client facts were independently verified. No real customer-facing release was observed or authorised.

## This bounded integration

New clean committed module `empire_os/enterprise_report_http_guard.py` makes one standard response wrapper for `json`, `html`, and `markdown`, internally calling the existing pre-render validator and its guarded render wrapper. It **deep-copies** the report before validation and rendering. It returns JSONResponse / HTMLResponse / PlainTextResponse with `Cache-Control: no-store`, `X-Content-Type-Options: nosniff` only for internally coherent, **unverified** investigative drafts. Tampered/unsupported report structure returns an HTTP 409 with **generic** `HOLD_ENTERPRISE_REPORT_EVIDENCE`, no report or source data leaked in the response. A 200 from these paths is **not evidence of client delivery rights, real economic performance or production-sale readiness**.

`tests/test_enterprise_report_http_guard_20261018.py` exercises the adapter and all three actual router paths via FastAPI's existing TestClient. Tamper cases cover fabricated verified findings, asserted financial actuals and forged client release approval on every route.

**Other-agent ownership:** The original dirty router is modified only through a pinned-exact-source SHA-256, narrow text replacements touching its report imports/three endpoint bodies. Its 55 original pending insertion lines and the other 184 unrelated dirty/untracked items are not committed or reset. A validated backup is retained outside the repository at the isolated worktree directory. The route integration is an **on-disk working-tree patch pending the owning agent's selective commit**; the new response adapter, independent tests and this document are committed independently. Do not claim Git HEAD alone includes the three enterprise-report route declarations. The owner must explicitly integrate and commit their original route file, renderer and report work after reviewing the minimal addition.

## Verifying on demand

```bash
cd /srv/empire_os
./.venv/bin/python -m pytest -q tests/test_enterprise_report_http_guard_20261018.py tests/test_enterprise_report_claim_guard_20261018.py
./.venv/bin/python -B -m scripts.preview_enterprise_report_evidence_readonly --read-only --format verify
```

For the HTTP API, test `http://127.0.0.1:8766/v1/predictive-revenue/product-workbench/enterprise-report`, `.../preview` and `.../markdown` **after** the service has loaded the router changes. Check HTTP 200 and no-store/nosniff headers for an unverified internal draft, and HTTP 409 generic evidence HOLD for a simulated falsified packet *through TestClient only*, not by injecting fabricated claims into the production service.

## Existing governance

- No customer delivery, verified client findings, source-verified actual revenue, terms, payments, email, CRM import, public URL, tenant permission grant, data source activation or database write.
- Restart the existing Founder read-only service **only after** review/tests and a preflight of its true systemd unit, without restarting adjacent production services. Check health and all three response headers afterward.
- **Unresolved external-access risk:** these are Founder-oriented internal routes, not customer report endpoints. Source-specific licensing, privacy, tenant scopes, access controls, finance reconciliation and real release conditions require separate review. Evidence truth is a necessary, not sufficient, condition for delivery.
