# Empire AI — Search department private release preflight
18 October 2026 | Canonical EmpireOS | Existing Search Command Centre

## Exact problem closed
The unified /department UI has been source integrated and tested (commit
3ef78870), but the running Search Intelligence API was not restarted,
and the Search Command Centre has no active production service and no
verified founder-specific identity gate. The public empire-ai.co.uk
gateway is NOT an acceptable substitute for the founder login.

This contribution **does not deploy** either component; it makes that
deployment dependency visible in one fail-closed release check.

## Additions
- Existing FastAPI route /v1/search/department/review now responds with
  Cache-Control: no-store and X-Content-Type-Options: nosniff on success,
  matching its already no-store failure behavior.
- New one-shot audit:
  scripts/review_search_department_release_preflight_20261018.py
- Tests:
  tests/search_intelligence/test_department_release_preflight_20261018.py
  tests/search_intelligence/test_department_snapshot_dashboard_20261018.py

From /srv/empire_os run:
  ./.venv/bin/python -m scripts.review_search_department_release_preflight_20261018 --read-only

The audit verifies exact source commit ancestry, clean scoped files,
existing search-api unit isolation on 127.0.0.1:8771, real loopback
Search Intelligence health, the new local endpoint's 404/200 state, and
the two corresponding public apex routes' absence (404). It never
executes a service restart, follows a redirect, submits an enquiry,
generates a web page, or attempts authentication. No private
exception payload or GSC query is printed. A public WAF 403 does NOT
count as established privacy; the check must see the expected 404.

## Interpretation
- API_SOURCE_READY_RESTART_REQUIRES_APPROVAL:
  committed in-source API passes safety checks, existing live unit healthy,
  public paths not exposed, but the running API doesn't yet include route.
  This is not authorization to restart.
- PRIVATE_API_ACTIVE_DASHBOARD_DEPLOY_HELD:
  read-only private GET returns verified schema and no-store, and public
  paths remain unavailable. Still no private dashboard login or release.
- HELD_RELEASE_PRECONDITIONS_NOT_VERIFIED:
  any source, service, route, public-edge or other prerequisite is
  incomplete or conflicting; stop and reconcile.

The output always marks
dashboard_private_identity_gate_verified=false,
dashboard_production_publication_authorized=false,
search_rankings_verified=false and revenue_verified=false.

## Gaps and safe path
1. Ask the founder to approve the *existing* loopback-only Search
   Intelligence API service restart. Run focused tests immediately prior
   to restart, then query GET /v1/search/department/review on 127.0.0.1.
2. Do NOT expose /department at empire-ai.co.uk while Search Command
   Centre has no deployed private service or verified owner identity
   protection. The app's current src tree contains no verified
   middleware/proxy for the department path.
3. Have the existing founder-console/auth owner explicitly design or
   connect the correct identity gate to the already built Command Centre;
   don't invent a password, cookie token, or bypass Gmail/Workspace auth.
4. Ask the founder for final visual/release approval. Publish through
   the existing controlled route only after verification of authenticated
   access, mobile parity, and public unauthorized refusal.

No new unit, reverse proxy, DNS, tunnel, paid service, password,
database migration, outbound marketing or public website change
was introduced. Other agents' founder dashboard files were untouched.
