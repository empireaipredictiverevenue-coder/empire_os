# Empire Research + Empire Agent — guarded Founder Console continuation

**21 October 2026. Isolated Research-owner worktree, not a production release.**

## Exact source and immutable baseline

- Start: `review/brokerage-us-uk-deep-research-owner-20261021` at `9549f0278`, clean before this implementation. Existing Empire Research, Empire Agent, original-source research harness, Search Fabric, Founder Console, CRM and source-intelligence engine reused, not duplicated.
- Production baseline changed during this work: initially `/srv/empire_os` HEAD `cc8691c34` with **197 dirty changes**, later independently observed HEAD `329b4303e` with **195 dirty changes**. Other agents are active, so pin a fresh live production HEAD/dirty-path inventory at release time. Founder Console owner files are already modified by other work; never checkout, reset, cherry-pick, overwrite or stage them indiscriminately.
- Existing services `empire-founder-dashboard-api.service` and `empire-founder-console.service` were active on `127.0.0.1:8766` and `127.0.0.1:3001` respectively. Current production Research route: HTTP **404** (`GET /v1/founder-research-products/catalog`), deliberately **not deployed**.

## Prepared isolated implementation

- A new Founder view `/founder/research` uses the **existing** Next.js Search Command Centre app, not an independent app, account or CRM. Offers Empire Research and Empire Agent, UK/US/both, 6 configured niches, speed/balanced/quality, original-source evidence and the six-step Agent receipt display. No action runs on page GET.
- FastAPI `GET /v1/founder-research-products/catalog` + **POST** `/v1/founder-research-products/preview`; previous GET preview removed. The router validates exact supported fields, forbids extras, enforces one executing job per API worker and a 60-second minimum interval per verified Founder subject. No tool shell, scheduled automation, DB write, proposals, publishing, emails, money or commercial authority.
- Every API endpoint requires a **valid Cloudflare Access JWT**: RS256 JWK signature, exact issuer, configured audience, expiry, issued-at and exact pre-approved Founder `sub`. Neither a browser claim, an email header, loopback address, nor a generic Cloudflare Access user constitutes Founder authorization. Settings `EMPIRE_FOUNDER_CF_TEAM_DOMAIN`, `EMPIRE_FOUNDER_CF_ACCESS_AUD`, and `EMPIRE_RESEARCH_ALLOWED_FOUNDER_SUB` must be supplied by existing authorised identity owner through protected configuration; missing values **fail closed (503)**. Do not put JWT, sub or keys in repository or logs.
- Browser POST bridge additionally requires exact configured HTTPS `EMPIRE_FOUNDER_RESEARCH_ORIGIN`, browser same-origin fetch metadata, JSON only and <=1024 request chars. It passes the Access JWT only over server-side loopback; Python independently verifies it. Browser never receives that token from API responses.
- Original page budgets: speed 1, balanced 2, quality 3 per country, maximum 6 cross-market. Optional fresh Search Fabric discovery is separately requested, uncached, max 2 queries per country/4 per operation; search candidates are **never** independently admitted evidence or licensed for customer use. All results remain editorial-held.
- Original source passages are SHA-256 bound and capped at 165 characters and 25 words; optional local model critique can see only bounded validated passage anchors, never entire pages, and returns **untrusted, question-only** editorial suggestions. Unsupported conclusions are held. No model-generated sales claim is approved.
- Tests: focused original+security+Search Fabric regression **117 passed** on 21 Oct with one unrelated Starlette/anyio deprecation warning. TypeScript `tsc --noEmit`, targeted ESLint and `git diff --check` all passed after the UI/fresh-discovery changes. An **isolated production Next.js build** passed with Next 16.3.5 `next build --webpack` (new dynamic `/founder/research` and `/founder/research/execute` routes included). Default Turbopack rejected the temporary out-of-tree dependency symlink used only for test reuse, not application code; the normal owner-controlled release must still validate its own dependency installation. A temporary isolated `127.0.0.1:3098` smoke showed unauthenticated page **LOCKED**, POST execution without verified origin/session **503**, and GET execution **405**. The temporary preview process was stopped and dependency symlink removed. No production service restarted or revenue action taken.

## Current fresh discovery and source custody

A real uncached existing Search Fabric run on 21 October returned:

| Sector/market | Fresh search result | Evidence admitted |
| --- | --- | --- |
| Dental / UK | Five candidate links after niche-relevance filtering | **0** |
| Dental / USA | Provider returned no sufficiently relevant candidate | **0** |
| Roofing / UK | Provider returned no sufficiently relevant candidate | **0** |
| Roofing / USA | Provider returned no sufficiently relevant candidate | **0** |

UK candidate URLs, **unadmitted**: `https://universitydental.co.uk/`, `https://dentalimplantcentrebirmingham.com/birmingham-dental-centre/`, `https://alldentists.co.uk/dentist/birmingham-dental-specialists-dental-implants-birmingham`, `https://www.bpidental.co.uk/`, `https://www.implantly.co.uk/dental-implants/locations/birmingham-full-mouth-dental-implants`.

An independent on-host real-page run of the **original reviewed dental catalogue** (not these newly discovered links) inspected 3/3 US and 3/3 GB originals and 16 bounded short passages; Agent status `WORK_COMPLETED_FOR_EDITORIAL_REVIEW`, Research-editorial status `AWAITING_OWNER`, customer delivery `BLOCKED`, writes/outbound false. Country evidence fingerprints: US `e7fa7c5401b8d5b3a1e71f34e869028b8213528b7cb781ac10f90b259d198323`, UK `e8c154821296dfe044e4bd7c930329bb982625d2c6c49381a651323c35fe5ad7`.

**These links are Search Fabric discovery candidates only.** No independent original-page inspection, ownership/right-to-reuse, source context acceptance or signed editorial judgement has been performed for them. Do not automatically add these URLs to a scraper allowlist, claim verified market positioning, send messages or resell their material. `BRAVE_API_KEY` was not configured in the inspected research execution environment; do not infer it is missing everywhere. Official provider restoration belongs to the existing Search Fabric/secret owner. UK/US roofing, solar, HVAC, legal and property maintain independent sector-country intake requirements and **zero new sector-specific admitted sources** here.

## Original editorial queue reconciliation (read-only)

Using the *existing agency Research owner worktree* `/home/ubuntu/empire_worktrees/agency_acquisition_conversion_20261020`, original read-only scripts returned:

- `review_agency_editorial_decision_requests_20261020 --read-only`: `HELD_EDITORIAL_DECISION_REQUESTS`, **0 prepared requests**, **0 verified signoffs**, signer keys not provisioned, 0 source rights verified.
- `review_agency_worksheet_native_research_join_20261020 --read-only`: `HOLD_CANONICAL_RESEARCH_QUEUE_EVIDENCE`, **5 historical original DONE preflight receipts present**, exact current receipt mismatch `actual_work_receipt_identity_or_authority_mismatch`, current source fingerprint `30747dd118e70ccb11efaf205f90a42dc60d250b9d378c7999245c5d95f7790b`.
- The original source snapshot changed relative to five immutable DONE work identities, particularly `intelligence_request.agency_source_evidence_review.snapshot_fingerprint`. Firegang retains an original-source access hold (HTTP 403); Wonderist editorial review pending. These are **not** missing old completions and must not be rewritten or made current by skipping identity checks.
- **Only the actual Research owner** can create a new versioned current-source preflight via the existing agency Department queue, independently inspect source claims and reuse rights, and return a valid authorised Ed25519 signed Research-editorial decision for exact report revision/worksheet bytes. No signer impersonation, synthetic approvals or direct researcher self-signoff is permitted.

## Release / rollback gates — do not execute without owner approval

1. Independent existing Founder Console/identity owner verifies Cloudflare Access protection at the real external origin, exact intended Founder subject, audience and issuer, MFA, request-header custody and backend JWT signature validation with an actual logged-in Founder session; also verify unauthorised subject, missing token, expired token, cross-site POST and direct loopback attempts are denied.
2. Validate on a **single isolated staging instance** with bound service account and one worker. Check the exact POST body, active budgets, backoff/concurrency, source fetch failure states, no secrets in outputs, no server-only code shipped to browser, and no ability to reach tenant/public frontend without an approved session. A 200 from loopback alone is **not** authentication proof.
3. Before any production integration, capture exact source HEAD/compiled Next build, web/API systemd unit contents and enabled settings, snapshot/backup rollback artifacts and integrity checksums; inventory every path to be modified and reconcile the **currently dirty production paths** with their owners; do not assume the earlier count or HEAD is current. Never restore a whole dirty tree or replace unrelated changes.
4. Get explicit scoped Founder release approval for the affected service copies/build and guarded restart. Deploy only the approved isolated patch to the existing services, preserving `127.0.0.1` bindings, and run authenticated positive + negative readbacks plus public 401/403/no-exposure check. No new public research domain, route forwarding to unauthenticated users or tenant account authority.
5. On any failing gate: stop new research execution, restore only the recorded affected build/config/code paths from the captured baseline via original service owner, restart only if separately authorised, verify health and previous routes. Preserve original receipts and audit logs. Never auto-enable sales, research approval, outbound, CRM writes, money or scheduled agent action.

**Decision:** isolated implementation candidate ready for independent owner review; production access/deployment, real Founder-session activation and editorial release **remain HELD** until authenticated independent evidence and approvals.
