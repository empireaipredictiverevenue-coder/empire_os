# EmpireOS Affiliate Subdomain Ingress — Release Contract

Date: 2026-10-10
Status: **IMPLEMENTED + LOCALLY TESTED; NOT DEPLOYED/ACTIVATED**
Mode: OBSERVE, fail closed
Owner: Revenue Distribution / Affiliate Tracking under existing EmpireOS governance
Primary project document: `docs/commercial/MULTI_PIPELINE_AFFILIATE_REUSE_ARCHITECTURE_20261010.md`

## The reuse boundary

The existing first-party Cloudflare Tunnel currently has these configured upstreams:
- `empire-ai.co.uk` -> `http://127.0.0.1:80`
- `www.empire-ai.co.uk` -> `http://127.0.0.1:80`
- `mcp.empire-ai.co.uk` -> `http://127.0.0.1:8765`
- catch-all -> `http_status:404`

The proposed `partners.empire-ai.co.uk` hostname is **NOT in the live tunnel ingress**. DNS and TLS provisioning have not been verified. Existing `empire-cloudflared.service` and `empire-public-gateway.service` were active when inspected. Both were left untouched.

**Design decision:** reuse the existing tunnel and public gateway (FastAPI on port 80), with a future explicit `partners.empire-ai.co.uk` host-to-port-80 ingress rule, not a new reverse proxy, extra database, affiliate SaaS, Next.js runtime, independent tunnel or systemd worker. The main website stays a static Next.js export served by the existing gateway.

## Code delivered

- `empire_os/affiliate_ingress.py`: reserved affiliate hostname, strict raw Host parsing, duplicate Host denial, signed-token readiness *review* using existing `empire_os/affiliate_tracking.py`; allowlisted **review-only** target paths for PPL/PPC and SaaS; protected status endpoint and inert referral entrypoint.
- `empire_os/public_gateway.py`: existing FastAPI app includes the router, protects `partners` Host from leaking primary landing, buyer/research/checkout/A2A endpoints or avatar WebSockets, and adds no-store/no-index/no-referrer protections. Unrecognised or duplicate Host values are rejected at the HTTP boundary.
- `tests/test_affiliate_ingress.py`: valid/invalid tokens, cross-tenant and wrong programme, forwarded/duplicate/spoofed Host, correct and wrong domains, 404 on unapproved primary and subdomain routes, no redirects/cookies, Main Site regression and blocked avatar WebSocket.
- Core token/ledger preparation remains `empire_os/affiliate_tracking.py`; economic review remains under **existing** `multi_pipeline_review.affiliate_tracking` in `runtime/revenue_distribution/latest.json`.

The currently prepared HTTP surfaces (only if the gateway is later restarted with this code) are:
- `GET/HEAD /v1/affiliate/status`: returns *only* PREACTIVATION and false authority when the request Host is exactly `partners.empire-ai.co.uk`; otherwise 404.
- `GET/HEAD /r/{tracking_token}`: identical 404 for all hosts/tokens, **including valid signed tokens**. It does not decode the token, call the database, record a click, redirect, collect consumer data, issue a cookie, onboard a publisher or recognise revenue.
- On the partner Host, **all other HTTP paths** return 404, including `/`, `/buy`, `/roofing`, `/health` and checkout; avatar WS connections close 4404. This prevents mistakenly presenting the main site at the new hostname.

## Test/readback evidence

Existing server Python venv, command:
`PYTHONPATH=. ./.venv/bin/python -m pytest -q tests/test_affiliate_ingress.py tests/test_affiliate_tracking.py tests/test_public_gateway.py tests/test_lead_smart_public_coverage_api.py tests/test_owned_campaign_preflight.py tests/test_revenue_distribution.py tests/test_revenue_distribution_review.py`

Result: **179 passed**, 1 existing Starlette/anyio deprecation warning, 0 failures. TestClient readback confirms the partner Host returns 404 for root and any referral token and 200 PREACTIVATION for the special status endpoint; the ordinary Empire AI Host continues to return 200 at root and health. Python bytecode compile and `git diff --check` were run.

Do **NOT** infer production delivery from TestClient. The running gateway process still serves its pre-existing imported code until a separately authorised release/restart, and no DNS/tunnel rule currently targets the affiliate hostname. Live routing has not been tested or authorised.

## Release blockers (must be closed before a live referral)

1. **Commercial corridor:** one real willing publisher/affiliate, their verified canonical owner/source/website, opt-in and suppression status; exact referral product; a paying buyer explicitly accepting *external sub-affiliate* traffic **or** a real deliverable Empire AI SaaS product. Approved territory, rate, payable event, termination/dispute rules and relevant consumer disclosure/consent.
2. **Canonical source admission:** authenticated tenant source lookup in EmpireDB with verified ownership, trusted campaign IDs, signed approvals and current validity. Never let a token's claims or caller-supplied flags grant authority.
3. **Permanent click durability:** an approved minimal-privilege EmpireDB writer using the existing `public.commercial_events` ledger, deterministic event ID and idempotency, strict conflict rejection, exact post-write readback, source-level caps/replay controls and no split-brain retry.
4. **Operations/privacy:** protect signing secret in a root-owned/configured runtime secret mechanism (never in code, browser, static Next.js build, logs or docs); key rotation/revocation; investigate Uvicorn/Cloudflare request/access-log token exposure (raw `/r/{token}` paths must be redacted or replaced with non-sensitive opaque handles); bot/abuse limits, consumer consent, retention and privacy review.
5. **Tracking-to-economics:** verified caller/form acceptance or fulfilled SaaS sale; canonical payment evidence and reversal/dispute reconciliation; no double monetisation; publisher liability based on agreed commission and **collected** net revenue; separate approved payout flow.
6. **Deployment:** production-release code review, explicit founder approval for DNS/Tunnel changes and gateway restart, safe backup/rollback, host-specific Cloudflare origin routing to existing gateway, Cloudflare DNS record and TLS checks. Preserve the existing web, MCP and other tunnel routes. Prove in one controlled smoke that `partners` routes to the held status/404 while the primary and MCP routes are unchanged.

**Immediate next engineering unit:** reusable authenticated source-admission reader and durable click-event write/readback with strict tenant isolation and dedupe. Do not put a live redirect behind a simple environment flag; promotion should require real evidence-backed controls and a separate founder-approved release.

**Nothing activated here:** no migrations, DB writes, Cloudflare changes, secrets created, services restarted, domains published, publisher emails/sends, consumer forms, paid calls, active referral links, accepted payments or recognised affiliate revenue.

## 10 October 2026 — ledger idempotency and initial commit scope

The attribution event planner now writes **both** a deterministic UUIDv5 `id` and a stable `affiliate:attribution:v1:<sha256>` `idempotency_key` matching the existing unique `public.commercial_events.idempotency_key` index (already defined by EmpireDB migration 006). The key is derived solely from trusted tenant/source/programme/product/market/external-event identity and has no personal data. No new database migration is required for the event shape.

`compare_canonical_attribution_readback` provides **structure-only** exact-event matching, not authentication. It requires exact event identity, payload, timestamp, null money fields and event type; a pre-existing idempotency key with different content is rejected. Because this routine is pure and accepts caller-provided rows, it explicitly cannot prove that an authenticated canonical database session performed the read. Actual database insertion, canonical reader login, transaction conflict handling, independent readback and secure click collection remain held.

**Current focused test evidence:** 190 tests passed across affiliate tracking, affiliate ingress, commercial-event repository, public gateway, ZIP coverage, campaign-preflight and Revenue Distribution modules; one nonblocking Starlette deprecation warning. Tests exercised no live SMTP, public DNS edits, Cloudflare deployment, buyer traffic, money or production DB mutation. A narrow initial affiliate commit must stage the explicit relevant files only; the repository contains many unrelated tracked/untracked modifications.
