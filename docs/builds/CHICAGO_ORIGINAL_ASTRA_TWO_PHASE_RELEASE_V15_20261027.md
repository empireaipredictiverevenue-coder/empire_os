# Chicago Original ASTRA Gateway — V15 Two-Phase First-Publication Acceptance

**Date:** 27 October 2026
**Lane:** existing original ASTRA website / SEO / brand owners
**Worktree:** `review/chicago-original-gateway-owner-20261027`
**State:** REVIEW ONLY, NOT LIVE, NO OWNER AUTHORITY FORGED

## Defect removed: circular first-launch requirement

V12 initially required `site_owner_live_readback_verified=true` **before** the first Chicago HTTP response would be allowed. That is logically impossible for a previously unpublished page, and can push operators to forge a readback flag. V15 fixes this at the owning code integration PR rather than adding another publishing system.

### Phase A — authorised first publication, after real owner approval

The existing `owned_campaign_release.released_html()` retains the original five-release check. It can admit exactly one additional source-hash-pinned Chicago page **only if all** of these already exist independently:

- Original five-released-campaign SHA readback and all five incumbent route identities remain intact.
- Original SEO/content, brand/media-rights and website/release owner decisions, independently sourced into existing protected owner-custody files (synthetic test role receipts are not real authorisation).
- Exact V10 source draft SHA `3ee2f8d08d12d306ab3842b3cb5b041d34fb340f2f6a8d8a898821b2200293a0`.
- Exact site-owner staged HTML at `apps/empire-public-site/out/research/campaign_ce77b7b6230b2c29f8ede779.html` matches the proposed `deployed_html_sha256`.
- Original owner release receipt binds `original_site_owner_staged_export_verified=true`, `staged_export_sha256=<deployed_html_sha256>` and `original_site_owner_release_approved=true`.
- Noindex remains enabled, no form/script/paid/outbound/checkout authority. No new service, database, webhook, tunnel or second website.

**Do not require prior live HTTP proof at this stage.** It's a pre-publish condition that cannot exist yet. The original release owner must independently approve and deploy Phase A via its existing controlled runbooks.

### Phase B — independent original-site LIVE readback after first HTTP 200

The separate read-only `empire_os.microsite_original_release_readback_v15.verify_original_owner_site_readback` checks the original first-party origin `https://empire-ai.co.uk`, using GET and HEAD against all five existing campaign routes plus the new one. It refuses to send any remote request without the Phase-A approved local staged HTML.

For all six, it checks HTTP 200, cache `no-store`, HEAD parity and **byte-for-byte match** against the original site-asset reader. For Chicago it further checks noindex and absence of forms/scripts. It fails immediately if an original incumbent changes or any route cannot be verified. It never sends a request to arbitrary external domains, logs fake revenue or modifies the original release.

Only the original authorised site owner runs the one-command verifier *after* supervised publication and writes its receipt into private EmpireOS evidence:

```bash
cd /srv/empire_os
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/srv/empire_os \
  /srv/empire_os/.venv/bin/python -B \
  scripts/verify_original_chicago_live_http_v15.py \
  --root /srv/empire_os \
  --output /home/ubuntu/empire_releases/chicago_original_site_owner_live_readback.json
```

This command cannot succeed on current production, because genuine owner receipts and the deployed HTML do not exist; no network calls should occur before the staging gate passes.

The returned `ORIGINAL_SIX_EXACT_GET_HEAD_READBACK_PASS` result is a **post-release** evidence receipt, not authorisation. No status or revenue may be assumed from simulation.

### Regression evidence

- Original first-publication gate and real FastAPI synthetic fixture tests: **36 passed**, one existing AnyIO/Starlette deprecation warning.
- Adversarial post-publication tests: initial no-approval blocks before network requests; exact six-route proof passes only using controlled fixture; 404/hash mismatch/no-cache/HEAD-with-body errors all reject.
- **118 tests passed** in the original ASTRA owner PR worktree; **72 passed** when the same gate/readback code was overlaid onto the isolated current-production-HEAD rehearsal (one pre-existing AnyIO deprecation warning in each run).

### Outstanding independent owner work

Draft GitHub review PR #148 remains unmerged. Original ASTRA owner still needs authentic SEO source acceptance, public orbital-A asset/photo rights, branch reconciliation with dirty production, single supervised live rollout and rollback plan. User's approval of a branding design is not a release signer. Do not activate paid traffic, lead forms or claim settled revenue.

Source issue: https://github.com/empireaipredictiverevenue-coder/empire_os/issues/138

External verification refuses redirects and off-domain targets. Actual current production, which has no owner-approved Chicago stage, returns a pre-network hold rather than pretending a successful live readback.
