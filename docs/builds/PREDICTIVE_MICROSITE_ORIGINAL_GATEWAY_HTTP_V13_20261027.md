# Chicago Microsite V13 — Existing Gateway HTTP End-to-End Release Rehearsal

**Date:** 27 October 2026
**Original owners:** ASTRA first-party website, SEO and canonical brand
**Source branch:** `agent/predictive-microsite-slopmonster-20261026`
**Status:** `ORIGINAL_GATEWAY_HTTP_REHEARSAL_PASS` — NOT DEPLOYED / no approval impersonation

## Why V13

V12 proved the optional owner addendum was fail-closed at the Python function level. V13 now tests the same proposal through the **real existing FastAPI `empire_os.public_gateway.app`**, including its live `GET /research/{campaign_id}`, `HEAD` responses, original five campaign renderer, security middleware and public sitemap.

No second route, server, service, DB, public URL or new autonomous agent is created. The real gateway's code remains untouched. A temporary `monkeypatch` of its original `owned_campaign_release.released_html` exists **only inside pytest** and restores itself after each test.

## Evidence from the real gateway

- First-party incumbent releases: **all five** original `/research/campaign_...` routes returned HTTP 200 HTML with original `Cache-Control: no-store`.
- Chicago proposed route (not deployed): `/research/campaign_ce77b7b6230b2c29f8ede779`.
- Chicago without owner approvals: HTTP **404** for both GET and HEAD, with no-store and original gateway security headers.
- Controlled test-only approval fixtures demonstrate the gateway *could* admit exactly this one page as HTTP 200 for GET and HEAD when a separately owned SEO, brand and website approval record and exact source/export/hash match. These are synthetic fixture records, **not** genuine approvals or live deployment evidence.
- With any one of the three simulated approvals absent: Chicago returns HTTP 404. Other unrecognised campaigns remain HTTP 404.
- Chicago remains absent from the public sitemap before release.
- Unmodified gateway CSP includes `img-src 'self' data:`, so an eventual approved source/brand asset can render data-URI images without asking for an extra host exception. Gateway also prohibits framing and caching.

### Source/release identity

- Candidate ID: `microsite_c4c5a13b626d293fe15c`
- Source preview V10 SHA-256: `3ee2f8d08d12d306ab3842b3cb5b041d34fb340f2f6a8d8a898821b2200293a0`.
- Original five release remains a separate immutable reader. Its `load_release()` exactly-five rule must stay unchanged.
- Dormant V12 owner-reviewed addendum in `empire_os/microsite_original_gateway_addendum_v12.py`.
- V13 original HTTP acceptance tests: `tests/test_microsite_existing_gateway_http_v13_20261027.py`.
- One proposed original-owner fallback patch is documented at `docs/builds/PREDICTIVE_MICROSITE_CHICAGO_GATEWAY_OWNER_PATCH_V12_20261027.md`.

### Reproduce full original-owner test

```bash
cd /home/ubuntu/empire_worktrees/predictive_microsite_factory_slopmonster_20261026
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
 -m pytest -q -p no:cacheprovider \
 tests/test_microsite_existing_gateway_http_v13_20261027.py \
 tests/test_microsite_original_gateway_addendum_v12_20261027.py \
 tests/test_microsite_original_site_owner_v11_20261027.py \
 tests/test_public_gateway.py
```

Original factory, site, SEO, commercial and V10–V13 suites: **311 tests passed** after final two additional V13 sitemap/security checks (one existing AnyIO deprecation warning).

## Remaining OWNER-only live work

The user accepted the image *design direction*, not an unconditional technical, legal or publicity release. SEO content/publication review is pending; public distribution of the original orbital-A artwork remains subject to the canonical brand owner; website owner has not installed the optional patch, prepared/deployed the exact site export or issued authenticated release records. The fact that a JSON fixture has `independently_approved=true` is **not an approval**. A separate original authority and file custody check is needed.

Only the original ASTRA website owner can supervise the controlled code adoption, real external HTTP 200/deployed asset SHA readback, rollback and exact five-route preservation, then let original first-party analytics/CRM/settlement readers measure genuine outcomes. Unknown remains unknown.

Track the exact remaining decisions on the **same** GitHub issue #138: https://github.com/empireaipredictiverevenue-coder/empire_os/issues/138

**Result today: tested existing-gateway compatibility; zero live website changes.**
