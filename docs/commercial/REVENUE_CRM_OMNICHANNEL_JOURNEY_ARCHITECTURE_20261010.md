# EmpireOS Revenue CRM — Omnichannel Journey Gap and Integration Contract

**Date:** 2026-10-10
**Status:** Implemented as **OBSERVE-only, local/tested, production activation held**.
**Owner:** Revenue CRM / Commercial Intelligence; original tenant-scoped EmpireDB remains the data authority.

## Product comparison — what to reuse, not fork blindly

Official Omnisend references:
- https://www.omnisend.com/features/
- https://www.omnisend.com/features/automation/automation-editor/
- https://www.omnisend.com/features/segmentation/
- https://www.omnisend.com/features/reports/

| Omnisend capability | Already in EmpireOS | Integrate / remaining gap |
|---|---|---|
| Dynamic behavioural segments | CRM read model, Conversation OS, closer and buyer pipeline views | **This slice:** deterministic evidence-bound lifecycle segments over existing CRM reads. Predictive/AI segments remain unverified, not claimed built. |
| Visual journey editor and branches | Existing founder/CRM interfaces and policy-driven agents | **Added in follow-up:** authenticated first-party browser canvas with draggable canonical stages, optional manual review/decision steps, bounded acyclic edges, mandatory gate-preserving connections and local versioned JSON import/export. Server-side persistence and executable workflows remain intentionally unavailable. |
| Email/SMS/push journeys | Governed outbound/consent & Omniroute capabilities | **This slice:** explicit no-send/no-subscription placeholders. No new sender, schedule, service or third-party routing. Owned sender config and marketing permissions are independent gates. |
| Abandoned-cart/intent recovery | CRM next-action, replies, customer success and governed followups | **This slice:** human-only dormant-conversation review from existing observed timestamp (not fabricated abandonment). |
| Marketing revenue attribution | Commercial event ledger, Search/A2A outcome attribution, Economic Memory | **This slice:** attribution explicitly UNKNOWN until joined to verified canonical ledger events; CRM price/deal probability never converted to revenue. Actual attribution join remains separate approved engineering. |
| Channel consent and suppression | Canonical suppression table and outbound governor | **This slice:** marks all channels BLOCKED until exact-tenant, person, channel, consent, suppression and sender evidence is available; no trusting unsigned request fields. |

## Architecture and trust flow

```text
Authenticated CRM principal -> dedicated EmpireDB per-tenant READ login
 -> canonical revenue_crm_prospects read/view
 -> current CRM next-action (REUSE, no duplicate closer)
 -> deterministic segment and graph overlay (this change)
 -> read-only /v1/revenue-crm/journeys/* and /prospects/{id}/journey-preview
 -> operator/visual canvas when authorised
    STOP: no address/consent, no send, no job, no CRM write, no payment
Separate future ledger reader -> observed conversion + verified recognized revenue
```

Data sources: existing tenant-authenticated CRM repository only. No new DB tables, Supabase, provider accounts, email data sync or browser-side identity claims. Existing CRM router handles 401 unauthenticated, 503 disabled/source unavailable and 404 unknown prospects. All journey previews fail closed if the canonical tenant or prospect binding is absent. Segmentation covers a bounded page of up to 500 records only; a partial page is **not** a complete tenant audience. Cross-tenant rows and duplicate records are rejected.

Outputs: graph metadata with node/edge labels, one prospect journey review, and aggregated segment counts. All are typed OBSERVED/REVIEW_ONLY *only with original canonical view evidence*; no forecast, AI-generated behavioural claim, production sends or payment. No raw email body or contact address is copied to these views.

Authority: OBSERVE / read-only. The router never accepts caller-provided tenant ID, consent, suppression-clearance or ledger proof to grant delivery or outcome authority. Consent, channel identity, suppression, provider availability, capacity, source rights and actual ledger economics require separate independently authenticated readers and founder gates. A route displayed in a journey is not execution authority.

Execution and idempotency: synchronous bounded HTTP GETs over existing CRM tenant reader, no timers, queues, mutable state, scheduling or retries; deterministic classification for a fixed canonical row. No uncontrolled discovery or duplicate sends. Invalid evidence is an explicit 503/blocked state, not an empty eligible audience. Test fixtures are not production facts.

Observability and rollback: graph schema version in every view; explicit blockers, source type, node IDs, zero authority and UNKNOWN realized revenue; remove isolated new routes/import if needed. Public serving requires the existing founder-approved authenticated CRM pilot and verified row-level/DB login tenant authority; this code alone cannot activate pilot login.

## Independent verification and completion

Must pass: journey segment and graph tests; suppression & no-consent false positives; stale timestamps; duplicate/cross-tenant batch rejection; lack-of-ledger revenue nonpromotion; unauthenticated route 401; disabled repository 503; tenant reader tests; existing CRM regression suite; git diff --check. Unit/TestClient success is **not** production tenant-login proof.

Delivery classification:
- **DONE in code:** evidence-only segment, next-action review, graph-ready workflow preview and aggregated per-page segments attached to the existing CRM router.
- **DONE in browser code:** interactive draggable journey layout, custom manual review/decision steps, connect/remove custom edges, cycle and mandatory-gate bypass rejection, canonical immutable gates, bounded JSON design import/export, a tenant-scoped segment preview panel and an authenticated route. Design metadata is not an executable workflow.
- **NOT DONE:** server-persisted versioned workflows, list/subscriber channel-consent storage, independently verified suppression joins, SMS/push send adapters, deliverability automation, third-party publisher traffic rights, actual commercial-ledger attribution joins.
- **PRODUCTION HELD:** tenant-authenticated live CRM pilot remains dependent on separate founder-authorised deployment and existing readiness gates. No active workflow journeys or new commercial/revenue outcomes are claimed.

## Interactive browser editor integration (10 October 2026)

The authenticated Revenue CRM router now serves the HTML canvas at `/v1/revenue-crm/journeys/designer` and its same-origin JavaScript at `/v1/revenue-crm/journeys/designer.js`. Both use the existing request-scoped tenant repository authentication and fail closed with 401 (missing authenticated principal) or 503 (CRM pilot unavailable). Neither endpoint opens a CRM database connection or mutates canonical records by itself. The document CSP allows scripts only from the same origin and prevents cross-origin connections, framing, forms and third-party assets. No analytics/third-party resources, storage, service workers, send or background timers were added.

The client only loads `/v1/revenue-crm/journeys/blueprint` and `/v1/revenue-crm/journeys/segments/preview?limit=100`. It can drag canonical graph stages (including keyboard arrow movement), create manual review/decision nodes, add/remove review-only edges, reset, and export/import a bounded, versioned local JSON file. There is NO deployment, auto-send, subscription, execution, scheduler, campaign activation or server-side design saving path. No tenant row/contact is included in the design export. Do not paste private customer names, email addresses or campaign secrets into design labels. The segment panel displays counts for only the authenticated, bounded page, never a subscriber audience proof.

The editor validates exact blueprint IDs/types/labels and locked mandatory edges, DAG acyclicity, 28-node/60-edge maxima, canonical gate preservation for every start-to-outcome path, and explicitly blocks falsified execution authority or server persistence in imported files. Custom edges cannot bypass the consent gate or any other required lifecycle step. The API graph now advertises an actual browser-local designer and separately reports workflow_server_persistence=false. Channel eligibility is NOT verified because canonical channel-consent and suppression readers are not yet joined; all channel actions remain BLOCKED_NO_SEND.

**Production truth:** The previous live contract probe returned CONNECTION_NOT_CONFIGURED, so this is locally tested, gated source code, NOT a verified live tenant console, and the design route cannot be assumed publicly accessible. Next permitted bounded engineering is independently authenticated tenant reader/consent-suppression join and then versioned tenant-owned design persistence with separate founder deployment approval. No live customer sends, CRM migrations, DB writes, traffic, settlements, or revenue occurred.

## 10 October 2026 — server-validated, append-only tenant design storage (prepared; NOT activated)

The initial browser-local journey designer is now backed by an independent Python schema validator (empire_os/revenue_crm_designs.py). It validates exact canonical lifecycle nodes/edges, immutable compliance and revenue gates, DAG paths, bounded labels/coordinates/size, no arbitrary contact identifiers or email/URLs, and refuses any execution, payment or messaging instruction. A client-supplied tenant ID is rejected as an unknown design field. The authenticated tenant must originate from the server's dedicated principal. JSON import and frontend checks are not considered an authorisation boundary.

Prepared migration migrations/empiredb/045_crm_journey_design_versions.sql creates **only when founder-approved later** an append-only revision table, tenant RLS with FORCE, unique tenant/design/revision, restrictive DESIGN_ONLY JSON checks, and SELECT+INSERT grants only to a separately provisioned NOLOGIN NOINHERIT empire_revenue_crm_journey_writer role. It deliberately requires role bootstrap and trusted session_user tenant resolver, and grants no membership or login to any existing actor. It creates no sender, subscriber list, consent grant, activated workflow or payment authority. In the current session this migration has not been applied.

Opt-in backend empire_os/revenue_crm_design_store.py uses a **different dedicated per-tenant LOGIN** from the CRM reader, validates its role membership/NOINHERIT safety and DB-resolved tenant, appends revisions inside a transaction, checks expected prior version for conflicts, and performs a second post-commit readback. A caller's local edit-counter is canonicalised to revision 1 / latest+1 on the server; no browser sequence is trusted as a DB state transition. Identical version retries are read as ALREADY_SAVED_SAME_CONTENT; conflicting concurrent versions are rejected.

POST /v1/revenue-crm/journeys/designs/drafts exists behind **two disabled-by-default** integration dependencies: authenticated tenant-scoped Postgres Revenue CRM read resolver and a distinct same-tenant dedicated design writer resolver. If the dedicated writer is not independently provisioned and injected, this route returns 503; no runtime activation or static page button is added. The browser still only supports local JSON export/import and never makes POST requests. This preserves founder-controlled deployment and no unintended DB writes.

**Consent/suppression status is still UNKNOWN/BLOCKED, not verified**. The current 040 tenant CRM prospect view deliberately excludes contact addresses and the global outbound_suppressions table cannot be safely joined without a separately authorised exact-person, purpose/channel-specific, tenant-safe read contract. No marketing subscribers, opted-in audiences, channel eligibility, outbound sends, SMS or push transports or revenue attribution are activated. Do not infer consent clearance from a design stored in the database.

Acceptance requires explicit founder approval of migration 045 and separately reviewed tenant writer identities, database role membership, RLS and rollback rehearsal, authenticated UI principal-to-DB binding, and consent/suppression data authority. The current commit is PREPARED CODE ONLY; never call production storage deployed based solely on unit tests.
