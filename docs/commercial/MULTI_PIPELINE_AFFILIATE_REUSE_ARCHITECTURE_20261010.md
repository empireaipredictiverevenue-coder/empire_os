# Empire AI — Multi-pipeline affiliate and revenue architecture (reuse-first)
Date: 2026-10-10. Status: ARCHITECTURE / OBSERVE. Owner: Revenue Distribution + Commercial Exchange. No live authority.

## Decision

**ONE shared EmpireOS control plane, SIX separate functional pipelines, ZERO newly required services.** The system is not another autonomous agent, CRM, affiliate payout database or traffic network. Extend existing readers, queues, documentation and Founder console only. Do not resurrect retired SQLite monetization or create an independent "publisher database." Vendor OSS should be used as small replaceable adapters only if a measured gap remains.

### System graph

```text
Sources / programmes / inbound email / owned SEO / contractor channels
  |  P1 Buyer demand   |  P2 Publisher supply   |  P3 Owned organic
  |  P4 SaaS affiliates|  P5 Conversion/fulfilment| P6 Revenue/learning
  +-------------------------+------------------------------------------+
                            |
          EmpireOS shared governance / source identities / evidence
          EmpireDB (canonical) + CRM + suppression + consent + approvals
                            |
           Campaign format and corridor decision (KEEP SEPARATE):
           owned organic PPC | owned PPL | third-party source PPC/PPL
           | contractor/business referral to paid Empire AI SaaS
                            |
           P5 accepted payable buyer event OR verified SaaS sale
                            |
           P6 collected payment + fulfilment + publisher cost/liability
               + realized contribution + Economic Memory
```

### Pipeline register / reuse contracts

| ID | Pipeline | Existing entrypoint / producer | Output and honest readiness | Independent blocker before live money |
|---|---|---|---|---|
| P1 | **Paying buyer demand** | `scripts/run_buyer_scout.py`, existing buyer scout timer, `empire_os/commercial_relationship_registry.py`, `runtime/buyer_network_intelligence/commercial_relationship_registry_latest.json` | Buyer-specific demand programme, *verified* buy-box, source permission, geography, rate and payable event | Lead Smart/Connexis/LeadBank/Validated publicity or replies DO NOT equal approved first-party or sub-affiliate traffic |
| P2 | **Publisher supply recruitment** | `docs/commercial/PUBLISHER_SUPPLY_RECRUITMENT_EVIDENCE_20261010.json`, founder-approved Gmail history, existing `empire_os/revenue_distribution_review.py` | Independent opted-in site/source identity; owned SEO audience and permitted referral format | Need partner response, verified owner, source and programme approval; do not resend hard-bounced GetTradesmen or treat PavementCalculator paid-only reply as fit |
| P3 | **Owned organic lead/call acquisition** | Existing organic-search recovery timer, search/AEO/SEO modules, `apps/empire-public-site/src/app/roofing/`, `empire_os/traffic_specialist.py` | First-party audience and buyer-reviewed landing. PPL form and PPC calls are **separate** products | Consumer PPL intake is not production-verified: legacy `ppl_service.py` and `lead_intake.py` use SQLite; migration 025 serves research enquiries, not sellable consumer PPL |
| P4 | **B2B SaaS affiliate/referral acquisition** | Existing publisher review, commercial product catalog, founder CRM and fulfilment; contractor audiences only | Tagged referral to real Empire AI software demo/order with original referring publisher identity | Product must be live/deliverable; seller and referrer terms, validated attribution, settled SaaS revenue needed before earned commission |
| P5 | **Conversion, routing and buyer fulfilment** | `empire_os/buyer_pilot_assets.py`, Commercial Exchange, buyer capacity, existing suppression/consent, fulfilment orders | Individually accepted call, lead or SaaS order only after source/territory/terms/caller-ID/consent checks | No shared default buyer number, live forms, automatic PII postbacks, invented payout, duplicate sale of same enquiry or inherited buyer rates |
| P6 | **Attribution, settlement and learning** | `empire_os/commercial_exchange_contract.py`, commercial events, Revenue Exchange, `empire_os/economic_memory.py`, OpenTelemetry already installed | Source -> accepted event -> collected payment -> obligation/cost -> realized contribution -> learning | Do not use `empire_os/affiliate.py` SQLite tier defaults; a click, invoice or uncollected payout is not revenue |

## Explicit revenue-mode separation

- **Owned PPC**: original Empire AI website + our first-party SEO; must match a buyer's explicit FIRST_PARTY_ORGANIC approval. Attributable call + verified outcome; no implied live route.
- **Owned PPL**: independently approved consumer contact/consent fields and state/ZIP; canonical EmpireDB consumer receipt must be built/reviewed before *any* activation. Existing business-prospect ingest is NOT a homeowner-intake substitute.
- **Third-party publisher PPC/PPL**: separate buyer permission for external publisher/sub-affiliate source, individual publisher/source ID, approved landing and consent, buyer-approved track/routing/postback. Lead Smart's direct first-party permission does NOT extend here.
- **SaaS referral**: external publishers market **Empire AI software to businesses**, not homeowner leads. Qualified paid sales with fulfillment and valid terms required before commission.

All paths use **one idempotent source/economic reference** and preserve buyer-specific payable event ID. Distinguish `visitor`, `source_referral`, `consented_consumer_enquiry`, `call_started`, `qualified_buyer_acceptance`, `payment_collected`, `publisher_payable_liability`, `realized_revenue`. Never allow an event or an unverified click to skip to collected payment. Never pay publisher commissions just because an invoice is issued.

### Pipeline state progression (no fabricated promotion)

`DISCOVERED -> SOURCE_REVIEW -> CONTACT_REVIEW -> CONTACTED -> REPLY_RECEIVED -> TERMS_REVIEW -> BUYER_OR_SAAS_MATCH_VERIFIED -> APPROVED_TEST -> LIVE_AUTHORIZED -> VERIFIED_PAID_OUTCOME`.

Different pipelines may be at different states. All identity, opt-out, consent, delivered email, contract, pricing, traffic, financial and fulfillment gates are independent. Each transition requires source/evidence ID + actor + timestamp + explicit decision where applicable. Hold when evidence is absent; do not infer authority from a model score, source website, old email or affiliate registration.

## Open-source component decision — **no big build**

| Project | Licence (verify installed release before packaging) | Purpose | Decision |
|---|---|---|---|
| Existing Python, PostgreSQL/EmpireDB, BeautifulSoup, OpenTelemetry | Already inside EmpireOS; OTel open-source | Identity/evidence, canonical data, review, tracing | **USE NOW; already present** |
| [Scrapy](https://github.com/scrapy/scrapy) | BSD-3-Clause | Respectful bounded first-party publisher site sweeps; rate limits/robots/terms; direct public evidence only | OPTIONAL **only if** current search/source probe repeatedly misses attributable publishers; don't add crawler timer |
| [RapidFuzz](https://github.com/rapidfuzz/RapidFuzz) | MIT | Fuzzy candidate **review** for near-duplicate business names; never authoritative identity or suppression | OPTIONAL tiny library, benchmark vs existing normalized exact-domain matching first |
| [Node-RED](https://github.com/node-red/node-red) | Apache-2.0 | Visual read-only internal workflow operator for multi-lane pipelines | **DEFER**: duplicates Astra/our existing schedulers; only if founder actually needs manual visual debugging after first pilot |
| [Temporal](https://github.com/temporalio/temporal) | MIT (server) | Durable long-running *post-approval* retries and evidence-bound workflows | **DEFER** until proven crash/restart/resume problem; its server/database/worker operations are significant |
| [listmonk](https://github.com/knadh/listmonk) | AGPL-3.0 | Opted-in publisher newsletters and consented marketing updates | **DEFER** until owned mailbox, source consent and separate purpose-limited mailing list. Not a cold-email/suppression bypass |
| [Windmill](https://github.com/windmill-labs/windmill) | AGPL-3.0 source; bundled CE and resale/embedding caveats | Self-hosted script UI | **DO NOT ADD** now; potential commercial/white-label licence and duplicate framework |
| [OpenMeter](https://github.com/openmeterio/openmeter) | Apache-2.0 | High-volume event metering | **DO NOT ADD** now; Kafka + ClickHouse + PostgreSQL footprint for use we can handle with canonical events |
| n8n | Sustainable Use License, NOT OSI open-source | Visual automation | **DO NOT REPLACE** existing EmpireOS execution; potential licensing if embedded into commercial white-label workflows |

These are possible internally hosted components; **not** commercial data providers, not proxies, and no dependency on a third-party SaaS. Each optional component needs security/licence review, a measured feature gap, rollback plan and founder approval before installation. No OSS stack is authorised to send mail, accept terms, mutate identity, route consumer PII or move funds. OTel is already installed; do not install again.

## Minimum changes, in order

1. **Now — organise, don't rebuild.** Reuse `scripts/build_revenue_distribution.py` as the existing dashboard data spine. Attach six lane-specific counters/readiness to the *existing* founder reporting only once verified; no new data store or cadence. Keep the present 12 external publisher prospects and linked Gmail drafts in the source-side queue. Preserve RoofPitch and Solar Briton pending; no duplicate follow-ups.
2. **Next business evidence — one real pilot.** Ask Connexis/LeadBank/Validated for written buy-box AND whether original traffic vs sub-affiliates is expressly permitted; request separate PPL/PPC terms. Focus immediate commercial effort on US roofing, not 12 niches.
3. **In parallel — source qualification.** Review roofing publishers with a verified zero-upfront performance arrangement, official contacts, consent, geo and ownership. Treat unsolicited bulk/low-intent traffic as unsuitable. B2B contractor-tool publishers can only be matched to a verified paid Empire AI software product.
4. **Only with independent approval — one route.** Prove identity/consent/source/rejection receipts, correct buyer IDs, no reused Lead Smart route, duplicate windows and traffic limits. A nonbillable controlled test is not a paid outcome.
5. **After collected money — measure.** Gross collected buyer/SaaS revenue less reversals, publisher contract liability, track/call/fulfillment expense = realized contribution. Only these verified records train source quality and commission recommendations.

## Completion gate (business, not code)

- One publisher and one monetizing programme positively qualify in **the same allowed market/format** (or one approved SaaS referrer and payable product).
- Programmes, legal/suppression/consent, event routing, settlement and independent founder authorisation are verified.
- At least one real attributed accepted event reaches **collected paid outcome** and Economic Memory with true margin, with no duplicate sale/payout.
- Until that happens, "12 prospects", "eight drafts", "sent email", "candidate buyer", "test passed", and "published affiliate terms" are NOT completed revenue.

## Current truth at 2026-10-10 review

Revenue Distribution: 12 research contacts; 4 founder-authorised external Gmail first touches; 1 recipient hard-bounced/canonically suppressed; 1 paid-only minimum $500 respondent excluded from zero-cash; 2 recipients waiting; 8 unsent drafts; 0 verified onboarded supply publishers; 0 realized affiliate revenue. Existing buyer and first-party routes have separate approval holds. Existing OpenTelemetry import is present; Scrapy, RapidFuzz and Temporal Python packages are **not installed** in the app venv. No new open-source services, database writes, migrations, sender activation, external spends, lead routing or account setups occurred in preparing this design.

## Implementation/readback — 2026-10-10 (non-activating)

The existing read-only `empire_os/revenue_distribution_review.py` now exposes `build_revenue_multi_pipeline_review`: six stable pipeline identities; source-availability diagnostics; separate homeowner-supply and B2B SaaS affiliate research counts; explicit missing business evidence; and false authority for sending, traffic, terms and money. The existing `empire_os/revenue_distribution.py:refresh_revenue_distribution` attaches it under `multi_pipeline_review` to the SAME established snapshot `runtime/revenue_distribution/latest.json`. No new service, public API, timer, workflow executor, lead form, CRM table, data connector or payment route.

Focused verification on the server: 65 tests passed for `tests/test_revenue_distribution.py` and `tests/test_revenue_distribution_review.py`; Python compile and `git diff --check` passed. Existing read-only snapshot rebuild passed. Independently read back: 6 pipeline identities, 12 researched external publisher records in two supply types (10 homeowner-referral candidates, 2 contractor/B2B referral candidates); 2 previously contacted sources waiting; 0 enrolled; 0 recognized publisher revenue. This **does not mean 10 qualified leads**, 10 approved suppliers, or 2 active SaaS affiliates. Economic Memory is correctly held without payment proof.

The programme remains OBSERVE. Source discovery exists; partner qualification and **money-making activation are not done**. No service install, new scheduling, database migration, production service restart, outbound message, live call/form routing, contract acceptance, publisher payment or recognised revenue occurred during this change. Code remains uncommitted alongside other existing worktree edits and needs a narrow integration review before a later production release.

## Affiliate tracking core — code delivered 10 October 2026

**Source-file salvage:** `empire_os/affiliate.py` supplies the concept of `?ref=` publisher tokens and click/commission records, but it is **legacy SQLite and must never be the payer/monetisation implementation**. No currently searched Python caller imports its functions. The new implementation is `empire_os/affiliate_tracking.py`; it uses Python standard-library HMAC/JSON/UUID and is integrated only as a zero-authority capability in the *existing* `empire_os/revenue_distribution_review.py` and `runtime/revenue_distribution/latest.json`. It does not install any tracking service.

**Built and independently tested:**

1. `AffiliateBinding` carries an explicit tenant reference, publisher/source ID and domain, buyer or SaaS programme ID, exact PPL/PPC/SaaS product format, country, and independent booleans for source ownership, terms, source and sub-affiliate permission, privacy/consent and founder launch authority. No commission percentage defaults.
2. `mint_tracking_token` and `verify_tracking_token` are **pure** signed referral token codecs: HMAC-SHA256, an explicit 32+ byte secret, up to 30-day TTL, caller-provided opaque nonce, tenant/source/programme/format/country/domain binding, constant-time signature check and no raw phone/email/IP or secret in output. These do **not** enable a public link or route. Test fixtures alone mint tokens; no real publisher tokens were issued.
3. `review_affiliate_outcomes` validates bounded source-bound claim events and canonical evidence reference shapes, blocks wrong market/format or invalid amount/reversal, holds replayed/conflicting event IDs and repeated opaque customer subjects/buyer acceptance refs. It only supplies a *provisional, nonpayable* commission review from separately claimed terms and amounts; it never certifies payment, performs canonical joins or books payable liability.
4. `prepare_canonical_attribution_event` produces a deterministic UUIDv5 row proposal matching **existing** `public.commercial_events` (event_type `affiliate_attribution_observed`) with tenant/programme/source references and a privacy-safe HMAC subject key, null money columns, referral-token SHA256 only and explicit non-revenue flags. Crucially this is **not inserted**; a dedicated, trusted EmpireDB writer must do globally idempotent insert, conflict comparison and post-commit evidence readback before the event can be considered stored.
5. `affiliate_tracking_capability` surfaces honest stage/readiness under `multi_pipeline_review.affiliate_tracking` in the existing Revenue Distribution snapshot. The actual live snapshot readback reports 12 **researched** publisher prospects and three distinct product formats, not enrolled affiliates, live links, verified conversions or recognised revenue.

**Validation:** 93 focused tests passed (`tests/test_affiliate_tracking.py`, `tests/test_revenue_distribution.py`, `tests/test_revenue_distribution_review.py`), Python compilation and `git diff --check` passed; read-only Revenue Distribution refresh/readback passed. No extra database, migration, timer, deployed endpoint, real click, email, traffic, payment, publication or publisher registration. Code is uncommitted.

### Exact next implementation seam, no parallel rebuild

- **Canonical durability:** approved dedicated least-privilege EmpireDB event writer using *existing* `public.commercial_events`, with trusted tenant resolver, caller identity, stable source token identity, conflict rejection, post-commit readback and cross-format subject/buyer-outcome dedupe; security/architecture review first. Code currently exposes only a row **candidate**, not a write pathway.
- **Source/click entrypoint:** small first-party `/r/<token>` (or equivalent) on the existing Empire AI site, with a fixed allowlisted destination per approved campaign, server-side signed token verification, short retention/consent and no open redirect; no endpoint has been deployed or authorised.
- **Billable outcomes:** separately authenticated buyer callback / provider-verified call or form acceptance, SaaS order+fulfilment, and trusted collected USDT/BSC or agreed actual payment source. Link to canonical independent payment, reversal and fulfilment rows rather than self-attested JSON refs. One event cannot be sold/commissioned twice.
- **Publisher accounting/UI:** tenant/source-scoped read-only dashboard, unique payable event/currency and approved contract basis; commission liability only after independently settled cash and net-margin checks. Founder approval before financial writes/payout.
- **Pilot:** begin with one verified willing roofing publisher and a buyer explicitly permitting third-party/sub-affiliate traffic in that exact corridor, OR one willing contractor SaaS referrer with deliverable Empire AI software and a verified first sale. Under no circumstances reuse first-party Lead Smart rights for outside publisher traffic.

**Current delivery status:** reusable tracking/domain core and founder snapshot INTEGRATED + TESTED; durable writer, public referral clicks, conversion postback, buyer eligibility and actual payable settlement **NOT LIVE / NOT FINISHED**. This is intentionally a single bounded code addition with no new infrastructure, not a completed revenue-producing affiliate platform.

## Subdomain decision — dedicated affiliate ingress (2026-10-10)

**Recommended host:** `partners.empire-ai.co.uk`. This is the branded interface AND future tracking entrypoint (`/r/{signed_token}`) for the first pilot. Retain `empire-ai.co.uk` as the public SEO/commerce site and avoid an additional Next.js runtime. A later optional short-link host can be added only after a demonstrated need; one subdomain is sufficient initially.

**Reused hosting:** the already-active Cloudflare Tunnel and `empire-public-gateway.service` (FastAPI on local loopback port 80), with an explicit extra host ingress rule to the *same* trusted service, not a new Cloudflare account, tunnel, service, DB, timer or Caddy path. Host-specific route dispatch at the gateway must fail closed for the primary site and unexpected `Host` values. DNS and tunnel routing must be verified independently and must not be asserted from code presence.

**Safety:** no production affiliate signing key in Next.js, browser JavaScript, query logs or the public dashboard. Resolve signed, expiring tenant/source/campaign/format tokens only in the trusted backend; ensure no raw consumer identifiers in tokens; set `Referrer-Policy: no-referrer`, `Cache-Control: no-store`, `X-Robots-Tag: noindex`, and no open redirects. Destination routes must be fixed approved first-party paths (not caller-supplied URLs), with per-source buyer/source authority, privacy/consent, duplicate and campaign gates. Rate limits, replay controls and a durable EmpireDB source-click writer require separate integration. The public landing form is not a billable PPL intake. Subdomain presence never independently verifies click, buyer acceptance, paid outcome or payable commission.

**Current observed status:** existing tunnel and public gateway systemd units are active, but DNS CNAME answers for `partners.empire-ai.co.uk` and optional `go.empire-ai.co.uk` were empty at this check; **subdomain not provisioned / not live**. No DNS/Cloudflare route was created or changed. The existing static Next.js export cannot securely track on its own, but the existing FastAPI public gateway can implement the *later* subdomain-bound server-side route after protected changes and founder approval. Founder-visible revenue dashboard remains the existing Revenue Distribution snapshot.

**Next bounded work:** prepare a fail-closed, Host-checked `/r/{token}` router attached to the EXISTING FastAPI app with 404 by default and no external redirects, and test host isolation, no-cache headers and blocked unapproved sources; only then separately configure DNS/tunnel, HMAC secret management, existing-ledger event writer + verified readback and an approved first publisher programme. No public exposure, route activation, consumer data movement or service restart without explicit production approval.
