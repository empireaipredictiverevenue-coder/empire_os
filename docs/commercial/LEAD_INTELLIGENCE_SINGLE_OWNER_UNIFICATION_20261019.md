# Empire AI — Single-owner Lead Intelligence + Scraper + Waterfall

**19 October 2026 — approved consolidation of development work, not production service retirement.**

## One build branch
- Primary ongoing branch: `integration/lead-revenue-fabric-single-owner-20261019`
- Primary worktree: `/home/ubuntu/empire_worktrees/lead_revenue_fabric_unified_20261019`
- The branch merges the complete committed Lead Supply Intelligence feature `41227510` and our Scrapling/Waterfall work `4dbb6ab5`. No competing platform, DB, CRM, email or new scheduler has been created.
- The earlier Lead Supply and Scrapling feature branches remain intact for rollback; treat them as **superseded development entrypoints**, not operationally disabled agents. Do not delete their worktrees or stop unrelated production services.
- Founder intends **this chat** as the single continuation owner. It is not technically possible for this repository change to close or pause a separate ChatGPT conversation. Continue any further development against this unified branch only.

## Integrated real code
1. `empire_os/scrapling_source_evidence.py`: source-governed offline extraction from already-obtained directory HTML. Bounded, no network, no commercial resale claims.
2. `empire_os/waterfall_source_bridge.py`: vertical and source-rights review, firm-type checks, demand/source evidence and receipt-based provider-order proposal.
3. `empire_os/scrapling_contact_extractor.py`: optional real Scrapling static-HTML parser for contact pages, bounded inputs, malicious/hidden/script text excluded, dedupe and provenance.
4. `empire_os/site_crawler.py`: new `extract_offline_html()` method wired to optional extractor. Existing `crawl()` and production default remain untouched.
5. `empire_os/scrapling_waterfall_provider.py`: optional enhanced provider assembled inside the existing `Waterfall` engine. Reuses native Registry/Hunter classes and the original strict `ValidationGate`; an offline-only subclass raises if anyone calls `.enrich()` without a separately built authorised execution path.
6. Existing Lead Supply census, territory joins, MRR packages, CRM/founder projection, qualification and scores are preserved by merge from `feature/lead-supply-intelligence-20261019`.

## Verified staging checks
- Both feature histories were merged into an isolated integration worktree, no merge conflict.
- 265 targeted integration/regression tests passed on the unified worktree; one existing Starlette deprecation warning.
- Actual Scrapling CSS parser tested with a temporary isolated package under `/tmp/empire-scrapling-20261019`. The shared production Python virtualenv was **not modified**.
- No production server process restarted, no new live crawler activated, no EmpireDB writes, no outbound and no payments.
- Test counts are software tests, **not** verified production leads, live buyer seats or realised revenue.

## Follow-on work — same single owner
- Read-only real market source pilot with actual rights/robots/privacy verification, network egress controls and request budgets.
- Persist quality receipts keyed by canonical business, source and territory; add genuine dedup/identity resolution, not arbitrary fuzzy merges.
- Connect independently verified existing buyer capacity, lead qualification and economic outcomes; do not claim a qualified or sellable lead from a directory contact alone.
- Reconcile the Lead Supply full census and private dashboard with production **only** under existing service credential and release approvals.
- Keep insurance carriers/TPAs, brokers, legal practices and mass-tort law-firm B2B evidence separate from consumers, patients and claimants.
- Preserve `empire_os/waterfall.py::build_default_waterfall()` unchanged until there is a separately reviewed production activation plan.

**Authorisation:** BUILD/TEST in isolated worktree. NO production migrations, email sends, payments, public portal, service activation, contractual offers or destructive resource cleanup.

## Wave 3 — canonical business-identity reconciliation (19 October)

The unified branch now implements `empire_os/scrapling_identity_review.py` and
`scripts/review_scrapling_canonical_identity_20261019.py` in the SAME owner
worktree.

- Takes the already-validated, offline Scrapling source report, not a newly
  collected web page.
- Requires an independently authorised, complete, consistent **identity**
  snapshot with `id,business_name,niche,metro,phone`. The founder Lead Supply
  census uses `id,niche,metro,status` and is **not sufficient** to identify
  a specific company; it therefore fails closed if supplied to the matcher.
- Uses Empire's existing `acquisition_fingerprint()` only as an **observation
  idempotency key**. The fingerprint is not entity identity or permission to
  create a new prospect.
- Outputs `POTENTIAL_EXISTING_REVIEW`, `AMBIGUOUS`, `IDENTITY_CONFLICT`,
  `CROSS_MARKET_MANUAL_REVIEW`, `NOT_FOUND_IN_COMPLETE_SNAPSHOT`, or
  `HOLD`. It never outputs an approved merge, a verified canonical lead or
  a sellable customer contact.
- Prevents shared phones from merging two distinct businesses; requires
  business name, niche and metro agreement for even a proposed match;
  divergent phone evidence and duplicate canonical IDs are blockers.
- Recognises only the **already registered** `gb_recc_solar -> recc_solar`
  canonical source alias. All other source adapters are held pending explicit
  review rather than dynamically declaring registry data to be ingestible.
- Preserves insurance/legal/mass-tort firm-only scopes and source-permission
  requirements from `waterfall_source_bridge.py`.
- Performs **no live EmpireDB query** and no crawler call. The local input's
  completeness flag and snapshot receipt are operator claims; the CLI cannot
  independently prove a real production snapshot was complete.

### Example offline review (does not query EmpireDB)
```bash
cd /home/ubuntu/empire_worktrees/lead_revenue_fabric_unified_20261019
/srv/empire_os/.venv/bin/python \
  -m scripts.review_scrapling_canonical_identity_20261019 \
  --read-only \
  --source-report /tmp/reviewed_source_evidence.json \
  --canonical-identity-snapshot /tmp/complete_approved_identity_snapshot.json \
  --snapshot-ref read-only:approved-cohort-snapshot-receipt \
  --complete-snapshot \
  --vertical solar --target-kind contractor --jurisdiction GB-ENG \
  --identity-ref company:independently-verified-001
```
Use only permitted local snapshots; never put credentials in CLI arguments.
A HOLD or potential existing status is **not** a verified live business match.
Raw snapshot identity fields must remain under existing production access rules.

### Explicit authority split and remaining gates
- **Built / tested / committed in this wave:** no-write source-to-identity
  review, existing Waterfall integration, Lead Supply code merge, diagnostics.
- **Not established:** actual production canonical company match, real
  rights-reviewed live Scrapling fetch, recipient opt-in, qualified buyer
  demand/capacity, dashboard consumption of this new review, realised revenue.
- **No database writes or operational services** are initiated by this feature.
  Production deployment and any new snapshot-reader privilege need separate
  approval, not an inferred permission from passing tests.

## Wave 4 — Snipers + scanners (19 October)

The founder requested the existing snipers/scanners to produce live-relevant
results as part of ONE unified Lead Intelligence/Waterfall system.

**Observed production 19 Oct 12:13–12:19 UTC**:
- `empire-buyer-acquisition-scout.timer`: active/enabled, executes existing
  buyer-scout read-only research, with periods of poor search-source yield.
- `empire-buyer-acquisition-team.timer`: active/enabled.
- Search Fabric reported DuckDuckGo HTML/Lite HTTP 202 (rate/anti-bot), Mojeek
  403, fallback engine irrelevant-result rejections; existing circuit breakers
  already skip blocked engines. Never defeat provider blocks or assume a 202
  response is successful evidence.
- The current observed buyer-scout artifact was read directly from
  `/srv/empire_os/runtime/buyer_acquisition/scout_latest.json` with
  `--read-only`; at that moment there were 10 research candidates, 4
  `PRIORITY_RESEARCH`, 1 `REGULATED_HOLD`, 1 `RESEARCH_REVIEW`, and
  4 `SOURCE_HOLD`, with 2 homepage fetch failures. These are transient
  research snapshot counts, NOT verified opportunities or live sales.
  There were zero verified buyers or outreach approvals.

### Concrete addition
- `empire_os/revenue_sniper_scanner_review.py`: consumes the **existing
  running buyer_acquisition_scout.v1** evidence snapshot; deduplicates by
  corporate domain/lane (conflicting duplicates become hold), validates source
  state/time/authority, ranks enterprise/home-service B2B research via
  transparent observed proxies (not actual buyer intent), and holds
  legal/insurance/mass-tort without specialist review. It does NOT call
  `agents/lead_sniper_agent.py` or schedule anything.
- `scripts/review_existing_scanners_and_snipers_20261019.py`: read-only one
  shot to inspect **current existing production scanner evidence** (no API
  fetch, network, database, review queue write or email send):
```bash
cd /home/ubuntu/empire_worktrees/lead_revenue_fabric_unified_20261019
/srv/empire_os/.venv/bin/python \
  -m scripts.review_existing_scanners_and_snipers_20261019 \
  --read-only \
  --scout-snapshot /srv/empire_os/runtime/buyer_acquisition/scout_latest.json
```
- `empire_os/scanner_source_contract_bridge.py`: adapts bounded **legacy
  scanner.py-shaped observations** to current source-rights review. Existing
  US `dbpr`, `sunbiz`, `county-appraiser`, `permits`, `bbb`, `web-search`
  sources are HELD until source registry rights, business-only identity,
  privacy, origin and territory are proven. No fake source approval.
- Tests `tests/test_revenue_sniper_scanner_review_20261019.py` and
  `tests/test_scanner_source_contract_bridge_20261019.py` cover no outbound,
  no data mutation, source restrictions, freshness, dedup, regulated niches and
  preservation of existing scouts.

### Explicit do-not-activate warnings
- `empire_os/agents/lead_sniper_agent.py` imports legacy
  `empire_os.sb`, writes `empire_tasks`, relies on `/root/` and on
  historical scoring/urgency heuristics, and has discrepancies between the
  old module prose and current review-only implementation. Do **not** start
  it unchanged; that is not canonical EmpireDB review authority.
- `empire_os/reddit_sniper.py` needs valid Reddit credentials and rights;
  the keyword/engagement score is NOT independently verified company intent.
- `empire_os/neural_scout.py` and `empire_os/scanner.py` contain older
  SQLite/requests flows; source uses require source contract/governance.
- The Satellite Scanner's image heuristics cannot verify a roof is damaged;
  no drone/imagery-based claims or homeowner targeting may be sold.
- The separate personal-market/crypto *trading sniper* is not part of this
  revenue-lead scope and no live financial orders have been authorised.
- No new cron, systemd timer, outbound governor, production env credentials or
  production service restart were created.

### Next actions
1. Fix search-source reliability within the *existing* Search Fabric
   owner/provider terms, prioritising current authorised first-party sources
   rather than anti-bot workarounds.
2. Connect independent canonical buyer firm proof, compliance checks, business
   identity and real buying reply to the current reviewer.
3. After the approved source-contract and EmpireDB reader proofs, connect
   legitimately qualified *supply* business IDs to our optional enhanced
   Scrapling/Waterfall; buyer research remains on buyer-authority path.
4. Only then authorise bounded review-queue materialisation, dashboard
   consumption, and separately approved outreach/contract/financial actions.

## Wave 5 — cross-snapshot revenue sniper readiness (19 October)

**Concrete build**:
- `empire_os/revenue_sniper_dispatch_readiness.py`: read-only compatibility
  verifier for THREE independent production evidence populations:
  `buyer_acquisition/scout_latest.json`, `buyer_acquisition/review_readiness_latest.json`,
  `commercial_exchange/latest.json`. Strictly checks versioned contracts,
  age, active delivery state and reconciles buyer-seat/review counters.
  Distinguishes research priority from legally actionable buyer capacity.
- `scripts/review_revenue_sniper_dispatch_readiness_20261019.py`:
  bounded local-file CLI, zero credentials, requests, DB writes, systemd
  mutations, outreach, financial transfers or activated trade orders.
- `deploy/systemd/empire-revenue-sniper-observer.service` and `.timer`:
  **STAGED ONLY, NOT INSTALLED/ENABLED**. Proposes a 30-minute read-only
  snapshot inspection cadence without adding new scans; service has strict
  read-only filesystem and denied IP networking. Operator must separately
  approve production installation, review the service user and validate
  systemd sandbox compatibility first.
- `tests/test_revenue_sniper_dispatch_readiness_20261019.py` plus
  `tests/test_revenue_sniper_staged_observer_20261019.py`.

### Real read-only snapshot evidence (production, 19 October)
- Buyer scout research: 10 candidates, 4 priority research, 1 insurance/legal
  regulated hold, 4 source holds, 0 verified buyers.
- Buyer-review: 200 assessed, 0 review-ready, 200 held. Primary blocking
  reasons are low first-party-site evidence (90), no direct-buyer evidence
  (61), official registry identity mismatch (28), permit territory unverified
  (14), business identity incomplete (5), contact path absent (2).
- Canonical Exchange: 1,057 buyer-seat records blocked on commercial evidence,
  0 active seat capacity, 176 bounded supply inventory records, 0 allocated.
- These are **three separate populations** and none proves 10 + 200 + 176
  unique market opportunities. The report intentionally does no entity join.
- The diagnostics are historical point-in-time observations, not a live
  availability/price/revenue promise.

### One command (no live execution)
```bash
cd /home/ubuntu/empire_worktrees/lead_revenue_fabric_unified_20261019
/srv/empire_os/.venv/bin/python -m \
  scripts.review_revenue_sniper_dispatch_readiness_20261019 \
  --read-only \
  --scout /srv/empire_os/runtime/buyer_acquisition/scout_latest.json \
  --review /srv/empire_os/runtime/buyer_acquisition/review_readiness_latest.json \
  --exchange /srv/empire_os/runtime/commercial_exchange/latest.json
```

### Actual next gates
1. Improve first-party source reliability **within** the existing Search
   Fabric provider and robots/terms policies; HTTP 202/403/circuit-open is
   a block, not permission for proxy evasion or more aggressive retry.
2. Resolve independent corporate identity, official-registry/website conflict
   and relevant UK/US jurisdiction verification; obtain actual purchasing
   intent through lawful, authorised B2B contact.
3. Provide real direct-buyer commercial agreement, signed capacity and
   buyer-seat activation receipts to the owner of canonical Exchange.
4. Inspect the staged observer unit if automation is desired; it is not
   installed. The legacy Supabase sniper is still not eligible for activation.
5. Only when separate approvals and evidence exist may qualified contacts,
   reviewed offer drafts, fulfilment, payment and recognised revenue advance.

**Production authority:** NONE. This is existing evidence reconciliation,
not an agent instructed to fire outreach, deliver a lead or execute a trade.

## Wave 6 — legacy Lead Sniper canonical endpoint replacement (19 October)

**User directive:** replace the legacy Lead Sniper's old review endpoint with
our canonical EmpireDB review boundary. The original agent, scores, scopes
and `empire_tasks` review queue are preserved in the ONE unified branch.

**Exact changes**
- `empire_os/agents/lead_sniper_agent.py`: `_queue_review()` no longer
  imports/calls `empire_os.sb`, `sb.select`, `sb.insert`, Supabase or
  old `/root/empire_os` path. The agent's review path now calls
  `empire_os.lead_sniper_repository.LeadSniperRepository`, not a new CRM
  endpoint. The canonical table remains `empire_tasks` with
  `task_type='sniper_review'`, `status='pending'`.
- `empire_os/lead_sniper_repository.py`: `CanonicalDataGateway` from
  existing `gateway_from_environment`, **EmpireDB-only**, no fallback or
  dual-write. Review dedup is scoped to `task_type`, pending status and
  exact `payload->>url` through `DataFilter`. Bounded count and timestamps
  fail closed; writes, when independently enabled, require positive readback.
- Registered sources: `gb_recc_solar` and other entries with **identity**
  role and internal acquisition permission in `source_intelligence.SOURCES`.
  An operator receipt is NOT independent proof by itself. The source's
  jurisdiction, vertical scope and domain must agree, and any consumer/
  claimant/patient content is rejected. Unknown US legacy feeds and Reddit
  authors do not become business review records.
- Legacy public Reddit RSS and permit RSS fetches are **OFF by default** and
  require `EMPIRE_SNIPER_LEGACY_PUBLIC_FETCH_APPROVED=1` after their source
  permissions and relevance are reviewed. No crawling or API call was
  triggered in this change.
- Legacy alerts are also OFF by default: any outbound-style operator alert
  needs `EMPIRE_SNIPER_ALERTS_APPROVED=1`, and only after a canonical review
  task is actually queued. No SMTP, customer lead delivery, outreach runner
  or financial action was enabled.
- Import-time creation of `/root/sniper` and the obsolete SQLite/hub
  endpoint references were eliminated. Internal diagnostics now default to
  `/srv/empire_os/runtime/sniper` only when a running agent logs activity.
- `scripts/probe_lead_sniper_canonical_endpoint_20261019.py --read-only`
  verifies the existing canonical reader using a non-sensitive probe task
  URL. It NEVER inserts any task, approves a sender, or tests actual writes.

**Write authority remains OFF.** Runtime flags needed for a *subseparately
approved* canonical task-queue launch are both:
```text
EMPIRE_SNIPER_REVIEW_QUEUE_ENABLE=1
EMPIRE_SNIPER_CANONICAL_WRITES_APPROVED=1
```
These have **not been added to production configuration or enabled**.
Enabling them alone would still not prove safe production launch: first verify
the exact EmpireDB `empire_tasks` schema/privileges; guarantee atomic
idempotency under concurrent sniper cycles; independently verify real source
rights and privacy; decide approved source cadence; run a canary and inspect
the results; preserve suppression/outbound approval. The current client
read-before-insert/readback path is not claimed atomic across processes;
do not activate simultaneous writers without a DB-level uniqueness contract.
Separate per-vertical legal/insurance/dental review remains required.

**No proof:** Production agent enablement, a completed EmpireDB task insert,
live buyer commercial capacity, first-party company contact validation or any
revenue. Tests verify code behaviour using a fake canonical gateway. The
older supervisor registry may still refer to the old Supabase behaviour and
must not be used as launch authority without owner review.

**Actual no-write endpoint probe receipt (19 October 2026):**
`scripts.probe_lead_sniper_canonical_endpoint_20261019 --read-only`
returned `HOLD_CANONICAL_READER_UNAVAILABLE` with
`DataGatewayUnavailable` when run as the currently available ubuntu
shell on EmpireOS. No DB table read was verified; no secret is logged.
This is an unprovisioned/unauthorised reader in that execution context,
**not proof that the EmpireDB table is missing**. Do not activate queue
writes or the sniper daemon until the owner has provided a dedicated,
least-privilege EmpireDB task reader and a bounded read-only schema/ACL
probe passes. Preserve existing operational gates.

The new dedup checks all statuses of `sniper_review` with matching exact
`payload->>url` over the configured recent window, not just pending tasks.
It refuses to guess if multiple matching rows prevent a complete stable
decision. Serial read-before-write + readback is **not atomic across workers**;
a database uniqueness contract remains a launch gate.

## Wave 7 — Scrapling/Sniper to Lead Exchange private inventory (19 October 2026)

User requested a connected Lead Exchange showing real inventory. This is built
from **canonical EmpireDB-backed Exchange projections**, not counted crawler
results, speculative sniper hits, Reddit urgency messages or raw registry rows.

### One reviewed B2B intake chain
- `empire_os/scrapling_sniper_handoff.py` connects the existing reviewed
  `Scrapling` source report → `scrapling_identity_review` →
  `scrapling_waterfall_provider` → `lead_sniper_repository`'s review
  contract, in-memory, without network/DB writes/auto-send. Supports
  arbitrary bounded source record index, checked against that exact company's
  separately supplied canonical ID and independent provenance receipts.
- `scripts/preview_scrapling_sniper_handoff_20261019.py` is an operator
  read-only local-file proof of that full pipeline.
- Even the successful state `SNIPER_REVIEW_PACKET_PREPARED` is NOT a
  canonical confirmed identity link, sellable lead, converted buyer,
  newly inserted EmpireDB record or approved review-queue write.

### Private Exchange inventory feed
- `empire_os/lead_exchange_live_inventory.py` reads the existing
  `commercial_exchange/latest.json` produced by canonical EmpireDB
  `scripts/refresh_commercial_exchange.py`.
- Requires `empire.commercial_exchange_snapshot.v1`, OBSERVE mode,
  `canonical_backend=empiredb`, `source=canonical_empiredb_projection`,
  bounded lists, exact row/state reconciliations, unique canonical
  prospect IDs and a timezone-aware freshness stamp (6-hour budget).
- Displays selected count, blocked-evidence count, buyer-capacity waitlist,
  allocation candidates, allocated count, active buyer seat *records*, and
  market groupings. Missing market identities remain separately labelled
  unclassified evidence holds, NOT discarded.
- Displays only aggregate niche/metro/corridor counts; **never** emits
  prospect IDs, buyer names, private emails, personal details or raw
  source/scraper records. The source selected population is a bounded sample
  of qualified candidates, NOT the full EmpireDB lead census.
- Reviewed sniper packets can be summarized as separate pending research
  items; they NEVER add to canonical inventory or imply buying intent.
- Freshness means **recently refreshed snapshot**, not a streaming, atomic
  real-time orderbook. Price, buyer capacity, entitlement, delivery and
  binding sale remain independently gated. `delivery_ready_now=0`
  unless a future owner supplies an independently verified allocation/
  fulfilment authority receipt through a separately reviewed design.
- `empire_os/founder_lead_supply_api.py` now mounts the **private-loopback**
  `GET /v1/founder-lead-supply/inventory` route in the existing
  `founder_dashboard_service`. The public gateway is deliberately
  unchanged, and no new unauthenticated public catalogue is deployed.
- `scripts/review_lead_exchange_live_inventory_20261019.py --read-only
  --snapshot /srv/empire_os/runtime/commercial_exchange/latest.json`
  shows the current aggregate feed with no server restart or DB mutation.

### Direct read-only runtime evidence (19 Oct ~13:10 UTC)
- The existing source snapshot showed 176 canonical selected inventory
  records: 85 held for missing evidence, 91 overflow/no buyer capacity,
  0 allocation candidates, 0 allocated, 0 active buyer seats out of
  1,057 seat records. Snapshot rows grouped into 92 inventory market
  groups; the separate overall Exchange corridor count was 157 (buyer
  corridors also contribute).
- This count is **not** new revenue, 176 immediately marketable contacts
  or available-to-buy consumer data. No outbound or payment action.
- A passing API/unit test against the isolated feature branch does
  NOT prove the private founder service has been restarted with this
  code. The user-facing console route remains **staged until explicitly
  installed/reloaded through the existing production owner process**.

### Next production prerequisites
1. Run the separate protected EmpireDB census through its existing
   least-privilege reader before displaying full-platform lead totals.
2. Repair/provision dedicated canonical `empire_tasks` reader; read-only
   sniper preflight currently fails with `DataGatewayUnavailable`
   under Ubuntu's unprivileged execution environment.
3. Independently review source rights, business/website identity, and
   legal/insurance/mass-tort practice data restrictions. Add real
   source and buyer receipts without treating paper intent as sale.
4. Review the existing founder console's loopback/token boundary,
   deploy the new read-only inventory route as a minimal-diff release
   only after service ownership/activation approval.
5. Do not activate public self-serve inventory counters until current
   snapshots, fulfilled entitlement, paid buyer capacity and compliance
   evidence all justify accurate user-facing claims.

## Wave 8 — bounded RECC Solar source sweeps and private inventory reconciliation (19 October)

**Founder directive:** turn on eligible source scanners and start bounded
research sweeps to grow future canonical supply inventory. Keep existing buyer
scout and commercial Exchange timers intact; no new trading, paid traffic,
outbound or public lead-list resale.

- Live source audit: `gb_recc_solar` registered **verified** with
  `internal_acquisition` and `entity_resolution`, raw resale disallowed.
  `robots.txt` allowed the member-search and detail paths for the configured
  source agent. Existing canonical `crawler_runner --source recc_solar
  --dry-run --max-candidates 8` saw 8 candidate-quality passes, no source
  errors.
- `empire_os/recc_supply_sweep.py`: rotates across at most 40 RECC Solar
  member links; cap **8 member details per sweep, 32 per UTC day**,
  robots check, first-party HTTPS only, >=0.7s spacing, mutex and persistent
  source cursor. Compacts source results into a **private, permission-600
  internal B2B research ledger** with canonical/sale/outbound authority FALSE.
  No external website follow-up, consumers or claimant profiles. Business
  names and source detail URLs remain private evidence, NOT exported or
  sold as raw RECC directory data.
- `scripts/run_bounded_recc_solar_sweep_20261019.py` uses a required
  `--run-founder-approved` flag and bounded private runtime folder at
  `/srv/empire_os/runtime/lead_supply/private_recc_sweeps`.
- `scripts/review_supply_sweeps_and_exchange_20261019.py` compares the
  real **canonical EmpireDB selected Exchange snapshot** with the separately
  deduplicated source research ledger. It never adds research observations
  to canonical inventory or calls a DB writer. Counts are distinct.
- The existing `empire-buyer-acquisition-scout.timer` and
  `empire-commercial-exchange.timer` were observed ACTIVE and left intact.
- Two live founder-approved private source sweeps completed at ~13:34 UTC;
  **16 unique research observations**, no detail-fetch errors, no canonical
  prospect additions. The Exchange stayed 176 selected records: 85 evidence
  holds, 91 buyer-capacity overflow, 0 allocated/ready. The scraper
  result is not an assertion of new net canonical contacts.
- Under current `ubuntu` shell, `CrawlerProspectRepository.from_environment()`
  returns `DataGatewayUnavailable`: the shell does not have the protected
  EmpireDB connection context. Do not copy secrets or fake ingest counts.
  A dedicated existing-service credential and approved atomic canonical
  ingest path are required to turn source observations into prospects.
- Approved schedule proposal: four daily UTC slots (01:17, 07:17, 13:17,
  19:17), at most eight detail requests per slot, capped 32/day and
  lock-protected. Pin the executed code to an immutable Git commit snapshot.
  If a source fails robots, source-contract checks or daily caps, the scan
  stops without promoting or exporting any contacts.

**Commercial truth:** acquisition research growth != qualified inventory,
buyer activation, signed capacity, purchase, fulfilment or revenue.

### Actual scheduled release receipt — 19 October 2026, Ubuntu user

- A **single Ubuntu crontab** entry named
  `EMPIRE_RECC_SOLAR_SWEEP_20261019` was installed for
  `01:17, 07:17, 13:17, 19:17 UTC`. `cron` service observed active.
- Cron executes a pinned, detached Git worktree snapshot rather than the
  evolving agent branch. Original release was `962d0347`; latest hardening
  ensures the daily source-request allowance is *pre-reserved on disk before*
  the first network call, so interrupted fetches do not reset the cap.
- Both source detail batches finished: 8 + 8 = 16 distinct private RECC
  firm observations, 0 source detail failures; saved to the private research
  ledger with directory mode 0700 and data files 0600. This count is not
  a verified net increase to EmpireDB.
- The existing `EMPIRE_ASTRA_OBSERVER` cron entry was preserved and
  `empire-buyer-acquisition-scout.timer` and
  `empire-commercial-exchange.timer` remained active. No legacy
  broad-spectrum 72-hour crawler was started.
- The real read-only two-population comparison returned 176 **bounded
  Exchange selected** records vs 16 **research-only** observations.
  Allocatable/deliverable records: 0. No new canonical DB writes, sales,
  SMS/email outreach, lead purchase or buyer allocation.
- Cron installation is a source-research capability only. The next scheduled
  run has not yet been observed in service logs at the time of this receipt;
  do not claim ongoing source success until the job actually executes.
- To disable only this new job, edit the Ubuntu user's crontab and remove
  the two lines beginning with the marker `EMPIRE_RECC_SOLAR_SWEEP_20261019`
  and its immediately following cron command. Preserve ASTRA and other jobs.

## Wave 9 — eight researched official source connectors (19 October)

Founder directive: source new US and UK business-identity feeds covering roofing,
solar, HVAC, dental, insurance, legal firms and mass tort law firms, add them to
the unified intelligence stack and run approved bounded pilots.

**Existing** RECC Solar sweeper remains the only new daily scheduled source.
All newly researched sources are explicitly `production_status=research` with
`allowed_uses=("analytics",)` in `empire_os/source_intelligence.py`.
Source metadata does NOT grant automatic prospect import, outbound, scraping
rights or resale.

### Registered official source pack status
- `us_cslb_official_contractor_csv`: California CSLB free license-master
  CSV, roofing C-39, HVAC C-20 and solar C-46. Implemented **offline
  narrow file parser**, not arbitrary licence-search scraping. Require an
  independently downloaded official CSV and source-rights receipt;
  `empire_os/cslb_contractor_csv_source.py`. Current license state must
  be separately verified. Official: https://www.cslb.ca.gov/Onlineservices/DataPortal/
- `us_nyc_dcwp_home_improvement_companies`: NYC DCWP official Socrata API
  `acd4-wkax` (Home Improvement Contractor Licenses), **manual bounded
  company-only pilot** implemented with one limited 20-row query/day, active
  unexpired licences, discard individual-named records, no contact fields.
  This source only establishes general home-improvement licence observations:
  *roofing/HVAC/solar speciality is unproven*.
  https://data.cityofnewyork.us/Business/Active-Home-Improvement-Contractor-Licenses/acd4-wkax
- `us_cms_nppes_dental_npi2`: CMS NPPES public API, **NPI-2
  organisations only**, 8 per bounded query and two different selected
  geo queries per day maximum, no automatic cron. As CMS directs bulk
  users to its downloadable DDS file, do not use registry API for bulk
  lead harvesting. Ignore medical practitioners/patients and returned
  personal contact fields. A provider NPI does not prove licensure.
  https://npiregistry.cms.hhs.gov/
- `us_nyserda_solar_participants`: official NY-Sun participating solar
  contractor directory, research/individual company lookup only until
  automation/bulk rights verified. https://portal.nyserda.ny.gov/FindAContractor
- `gb_sra_firm_api`: UK SRA public law-firm data API, registration/key
  required; API attribution required. No individuals or claimant profiles;
  firm's mass-tort specialism needs separate practice-area proof.
  https://www.sra.org.uk/datasharing
- `gb_fca_insurance_firm_api`: UK FCA FS Register API (registration/key
  required). Its free lookup API is **single-entity, NOT bulk discovery**;
  bulk extract is a separately purchased service. Insurer/broker legal
  entity and regulatory status only, no policyholders.
  https://www.fca.org.uk/firms/financial-services-register
- `us_naic_carrier_lookup`: NAIC Consumer Insurance Search, manual
  per-carrier verification only; no approved bulk connector or consumer
  insurance records. https://content.naic.org/cis_consumer_information.htm
- `us_state_bar_firms`: US state bar individual jurisdiction firm and
  law-office licensing lookups. No fictitious nationwide lawyer data API;
  natural-person attorney search is not a qualified law-firm or mass-tort
  claimant source.

### Real bounded pilot receipts (EmpireOS)
- UK RECC Solar: 16 distinct private firm observations collected in two
  earlier licensed source sweeps.
- US CMS NPPES: **8 Dallas TX** + **8 Chicago IL** NPI-2 dental
  organisations, 16 unique organization research observations, HTTP 200.
- NYC DCWP: 20 sampled source rows, **9 company-format active licences**
  after removing individual-like/expired/no-company records.
- **Total 41 observations in three separate research pools**. The pools
  are not reconciled to the full EmpireDB company corpus and are not sold
  contacts; only their aggregated source research counts are combined.
- Existing canonical Exchange remains **176 bounded selected inventory
  records**, 85 evidence holds, 91 capacity waitlist, 0 buyer allocations
  and 0 verified immediately deliverable leads.
- Independent primary `CrawlerProspectRepository` still fails to obtain
  an EmpireDB connection under Ubuntu's current unprivileged shell.
  No new prospect inserts or claims of newly verified canonical inventory.

### Command references
```bash
# This one reads only private aggregate receipts, not company contact data.
/srv/empire_os/.venv/bin/python -m \
  scripts.review_multivertical_source_inventory_20261019 \
  --read-only \
  --exchange /srv/empire_os/runtime/commercial_exchange/latest.json \
  --recc /srv/empire_os/runtime/lead_supply/private_recc_sweeps/latest.json \
  --nppes /srv/empire_os/runtime/lead_supply/private_us_dental_orgs/latest.json \
  --nyc /srv/empire_os/runtime/lead_supply/private_nyc_contractors/latest.json

# Read-only source catalogue and access blockers.
/srv/empire_os/.venv/bin/python -m \
  scripts.review_official_vertical_sources_20261019 --read-only
```

### Launch boundary
Only the previous RECC sweep is **actually scheduled**; NPPES and NYC
were **manual one-time bounded pilots**. The SRA and FCA integrations
need founder-managed API registration and terms; NAIC and state bar
are manual checks; CSLB needs an official selected download file.
Do not enable placeholder URLs in legacy `contractor_scraper_agent.py`;
its `SOURCES` values include non-existent endpoints and its old hub
POST path is not canonical EmpireDB ingestion.

Next revenue-critical step: source-rights receipts, canonical company ID
and legal/entity status checks, protected EmpireDB ingest under existing
least-privilege service owner, then re-materialise Exchange and verify
buyer capacity. No paid traffic or external outbound enabled by this work.

## Wave 10 — Official source observations → existing EmpireDB prospect preparation

**Date:** 19 October 2026. Founder directive to continue connecting the
41 recorded official-source business observations into the actual canonical
Lead Intelligence and Lead Exchange architecture (no new database).

### Implemented
- `empire_os/official_source_canonical_preflight.py` reads the three bounded
  private observation ledgers from UK RECC Solar, US CMS NPPES NPI-2 dental and
  NYC DCWP home-improvement firms, validates each source provenance and
  outbound/data-use authority, and prepares eligible sources using **existing**
  `empire_os.prospect_ingest.prepare_candidate()` and
  `prospect_identity_keys()`.
- The canonical prep flow deliberately uses **buy_signal_score=0**. A firm
  in an official directory is a business-identity observation, not an
  interested buyer; legacy RECC code's high source confidence should never
  be interpreted as purchase intent in this pipeline.
- RECC: source `gb_recc_solar` has verified internal acquisition rights.
  Prepared candidates use existing native crawler `source=recc_solar`,
  `niche=solar`, `metro=United Kingdom`, source detail URL, conservative
  identity key and registered provenance. No unverified website is written
  into a canonical prospect.
- US CMS NPPES and NYC DCWP: their Source Intelligence source-contract
  entries remain `production_status=research`, `allowed_uses=(analytics,)`.
  They are **held for rights review**, regardless of NPI or public licence
  status. They cannot become canonical contacts or sellable inventory.
- Optional `--probe-canonical-reader` path reuses existing
  `CrawlerProspectRepository.from_environment().lookup_existing()` with
  a hard limit of 0–8 bounded read-only lookups (default 4). No calls to
  `ingest_atomic`, no new database or unapproved Supabase fallback. A
  lookup result of `new` is **not** interpreted as verified net-new
  EmpireDB prospect, buyer or inventory; actual atomic ingest is a later
  separately approved owner operation.
- `scripts/preflight_official_source_empiredb_20261019.py --read-only`
  consumes existing local ledgers, never fetches websites or reveals
  company/customer fields in its JSON response.
- `empire_os/founder_lead_supply_api.py` now implements private-loopback
  `GET /v1/founder-lead-supply/source-readiness` for aggregate observed,
  prepared, held, source-contract and rights reasoning counts. This code is
  staged on the unified branch; **the production service has not been
  redeployed/restarted with this route**.
- Tests in `tests/test_official_source_canonical_preflight_20261019.py`
  cover real canonical prep, fake bounded identity reader, no writes,
  zero buyer intent, aggregate privacy, source tampering, duplicate business
  observations and endpoint wiring.

### Verified source-ledger checkpoint
Read-only direct server probe on 19 October:
- 41 observed entries across 3 source pools.
- **16 UK RECC Solar** records prepared in memory for *canonical identity
  review* (not 16 approved new prospects).
- **25 US** observations held: 16 dental NPPES organisations + 9 NYC
  home-improvement corporation-format licences. Both sources require
  further acquisition-rights review.
- Optional real `CrawlerProspectRepository` reader returned
  `DataGatewayUnavailable` in this Ubuntu shell; no EmpireDB row-level
  reconciliation or prospect creation has been confirmed.
- Canonical Exchange remained at 176 bounded selected inventory records
  at its previously inspected runtime snapshot. These 41 observations
  have created **zero additional verified Exchange inventory**.

### Operator commands (read only)
```bash
cd /home/ubuntu/empire_worktrees/lead_revenue_fabric_unified_20261019
/srv/empire_os/.venv/bin/python -B \
  -m scripts.preflight_official_source_empiredb_20261019 --read-only

# Optional bounded EmpireDB lookup; currently holds without authorised DSN.
/srv/empire_os/.venv/bin/python -B \
  -m scripts.preflight_official_source_empiredb_20261019 \
  --read-only --probe-canonical-reader --max-lookups 2
```

**Actual pending activation gates:** source-data reuse rights for CMS/NYC,
independent corporation identity and niche/territory proof, existing
least-privilege EmpireDB reader credentials in a service owner context,
read-only exact-id lookups, separately approved atomic canonical ingest,
then Exchange refresh and buyer-capacity verification. No traffic spend,
public resale, automatic outbound, purchase or live trading.

## Wave 11 — Revenue-first B2B lead-gen qualification queue

**Founder instruction:** continue one unified Empire AI Lead Intelligence,
scraper/Waterfall and lead-generation build with commercial revenue priority.

### Concrete integration

- `empire_os/leadgen_revenue_activation_queue.py`: a new **read-only,
  no-network, no-DB** research-activation queue joining the existing:
  - `runtime/buyer_network_intelligence/founder_qualification_actions_latest.json`
    generated by **the already-running Buyer Network intelligence owner**,
    without cloning/displacing its buyer authority or rewriting its own files;
  - `runtime/commercial_exchange/latest.json`, the canonical
    EmpireDB-backed bounded selection of supply and buyer-seat states,
    validated through `lead_exchange_live_inventory`; and
  - optionally `official_source_canonical_preflight`'s aggregate
    RECC/NPPES/NYC research rights and identity-preparation counts.
- The joins are **industry tags only**, not company identity, buyer
  contract, or buyer geography. Exact niche tags roofing/solar/HVAC/etc.
  produce research-scope counts. `home_services` is intentionally
  NOT aliased to all niches or counted as corridor matching.
- Uses the Buyer Network agent's existing six evidence tasks, keeps
  a bounded 15-target default private Founder research shortlist,
  evidence checklist and only validated HTTPS first-party links.
- **No marketing spam:** no new outbound service, email/SMS send,
  browser crawl, CRM promotion, buyer-seat activation, pricing claim,
  inventory allocation, payment or trading.
- The score displayed as `founder_research_priority_not_buyer_intent`
  remains a prioritisation heuristic; even a perfect score does not imply
  a buyer, reply, accepted publisher, approved payout or contract.
- `scripts/review_leadgen_revenue_queue_20261019.py --read-only
  --include-source-readiness` runs the queue directly against the
  production snapshot files without touching their authors or DB tables.
- `empire_os/founder_lead_supply_api.py` has a new **PRIVATE, staged**
  route `GET /v1/founder-lead-supply/leadgen` for the existing
  founder-read-only service; it requires the service's existing loopback/
  login boundary to be verified prior to production rollout.
- `tests/test_leadgen_revenue_activation_queue_20261019.py`: guards against
  stale/malformed commercial inputs, duplicate domains, missing verified
  first-party signals, unapproved contact claims, spoofed URLs, unsafe
  raw contact leaks and false supply/buyer matching.

### Real current-state read-only checkpoint, 19 October ~15:46 UTC

- 25 real B2B **research** domains from the existing canonical buyer
  qualification-actions feed. All 25 in `EVIDENCE_RECOVERY`,
  **0** in `FOUNDER_REVIEW_ONLY`. Twelve have first-party buyer-role
  corroboration (not buyer acceptance or budget), 25 first-party due
  diligence snapshots report CURRENT, and three have independently
  retained first-party research URLs.
- Known gap categories: 25 compliance, 21 payout economics,
  19 integration/tracking, 10 contact/application route,
  3 active-buyer demand, 2 publisher acceptance.
- Sample highest-ranked review-only buyer research domains:
  `astoriacompany.com` (solar research), `cre8tivemarketingllc.com`
  and `px.com` (roofing research), `rvnu.com` (roofing research).
  These are observations of first-party/public profiles, **not** verified
  purchasers, approved counterparties or automatically sendable contacts.
- Canonical EmpireDB-backed bounded Exchange: 176 selected entries,
  85 evidence holds and 91 buyer-capacity overflow, **0** currently
  deliverable; all 1,057 observed buyer-seat records remain blocked
  for missing evidence. These represent separate source populations.
- Official source research 41 firm observations, including 16 RECC
  prepared for canonical **read-only review**; no verified net-new
  EmpireDB rows, no increment to Exchange inventory. These are not
  summed with buyer research targets to imply 66 unique opportunities.
- Latest Ubuntu shell still reports `DataGatewayUnavailable` when
  attempting to initialise the protected canonical reader. No write
  activation, no work-around by exporting production credentials.

### Why this is the next practical revenue step

The platform already discovers source companies and surfaces buyer-market
research. The immediate business blocker is a **genuinely buying** company
and a matching, verified, deliverable product. The queue tells the founder
which actual B2B buyer domains to investigate next, which evidence gaps
are known, whether matching niche supply exists *at aggregate level*
and why no email or sale has yet been authorised.

**Deployment state:** code and unit/API tests only. The new private
founder route is NOT live until the service owner deploys it after reviewing
the active auth and code ownership. No changes to production database,
web traffic cadence, SMTP or financial gates.

### Optional private runtime materialization

The new `--write-private` flag for
`scripts/review_leadgen_revenue_queue_20261019.py` creates an **internal
derivative** at
`/srv/empire_os/runtime/lead_supply/private_leadgen/research_queue_latest.json`
with mode 0600 inside a 0700 Ubuntu-owned private directory. The
`--read-only` flag continues to mean all upstream production snapshots,
buyer records, CRM, EmpireDB, payments and external services are unchanged.
The optional single derivative report is the only intentional local write.
Invalid/stale snapshots are HOLD and do not overwrite the last valid report.
This is not a customer or external lead list. Report includes verified
first-party **research URLs only** when provided by the upstream Buyer
Network owner, no personal recipient information, and no send authority.

Initial production snapshot computation on 19 October returned
`FOUNDER_RESEARCH_QUEUE_READY`, 25 research targets, 0 qualified buyers,
0 outbound-authorised contacts, 176 bounded Exchange selected records,
41 separate source research observations with 16 review-prepared and 25
source-rights held. The internal JSON was created and file permissions
read back as 0700 directory / 0600 report.

Proposed schedule: run the pinned, no-network/no-DB-write private derivative
twice an hour after its own immutable release commit; a task may only
materialise if the upstream Exchange and Buyer Network snapshots are both
valid and less than six hours old. Cron install/readback is tracked separately
from code commit; do not claim this code is deployed to a web service.

### Wave 11 deployment receipt — lead-gen private observer

**Verified operational state on EmpireOS, 19 October:**
- Lead-gen source commit `a0e55412` remains in the unified branch.
  Pinned immutable detached worktree:
  `/home/ubuntu/empire_worktrees/leadgen_revenue_queue_release_a0e55412`.
- The pinned code **executed successfully** against existing production
  read-only snapshots: state `FOUNDER_RESEARCH_QUEUE_READY`, 25 buyer
  research targets, 0 qualified buyers, 0 sender authority.
- New Ubuntu crontab task marker
  `EMPIRE_LEADGEN_RESEARCH_OBSERVER_20261019`: **:23 and :53 each hour**,
  `flock -n` to avoid overlap, 30-second timeout and no network/DB
  ingestion or email send. Runs the immutable code and atomically
  updates ONLY the private derivative report on successful preflights.
- Existing RECC Solar sweep cron preserved; ASTRA observer entry preserved;
  `cron`, `empire-buyer-acquisition-scout.timer` and
  `empire-commercial-exchange.timer` all observed active.
- Private runtime directory
  `/srv/empire_os/runtime/lead_supply/private_leadgen` is 0700 and
  the last-successful report `research_queue_latest.json` is 0600.
- **First unattended cron delivery NOT yet observed** as of this receipt;
  scheduling and manual pinned run are verified, not a future success claim.
- To disable only the new observer: remove the marker line
  `EMPIRE_LEADGEN_RESEARCH_OBSERVER_20261019` AND the single immediately
  following `23,53 * * * *` line from Ubuntu's crontab. Preserve all other
  crontab entries and systemd timers.
- This operation does **not** deploy/activate the staged private Founder
  API route, which still requires the existing UI/service owner to validate
  auth and service health before release. It also does not enable
  `empire_tasks` canonical sniper writing or canonical lead ingestion.

**Operational next gate:** independently verified buyer purchase/capacity
terms and protected EmpireDB business identity reader. A source score or a
research-domain first-party page is not a verified purchaser.

## Wave 12 — Canonical buyer-contact history reconciliation (19 October)

Existing Founder research must not treat already-contacted companies as new
cold leads. The unified agent reuses the already scheduled and read-only
`commercial_relationship_registry_latest.json` produced by the existing
Gmail evidence / Buyer Network owner, without duplicating its database or
altering the outbound governor.

### Implemented
- `empire_os/leadgen_contact_history_bridge.py` reads the existing private
  `empire.commercial_relationship_registry.v1` snapshot, scoped to the
  current 25-domain shortlist. It combines exact domain-level affirmative
  outbound/inbound and do-not-pursue evidence, without exposing recipients,
  private names, thread IDs or message content.
- `empire_os/leadgen_revenue_activation_queue.py` annotates each research
  candidate with its actual **existing-thread review**, **history
  unverified**, **do-not-pursue**, or **technical endpoint** category.
  Matched inbound responses appear first for manual follow-up research.
  A stale Gmail capture may still prove prior contact; no absence is
  interpreted as the address being clear for a new send.
- The newer upstream Buyer Qualification Actions snapshot introduced
  `independent_buyer_review_evidence` as an explicit outstanding gap.
  The unified consumer has an additive, held-proof interpretation instead
  of dropping the new requirement or touching the other agent's files.
- The private read-only Founder route and CLI accept the existing commercial
  relationship snapshot; use `--include-contact-history` with
  `scripts.review_leadgen_revenue_queue_20261019.py` to require this
  cross-check. Invalid or unavailable history is a HOLD on that path.
- No CRM, canonical buyer state, suppression table, outbound intent, email,
  payment, contract or prospect was changed by this reconciliation.

### Observed operational evidence
- Existing Gmail relationship snapshot: 58 thread evidence records.
  Commercial relationship registry: 259 identity relations, read-only,
  generated 19 October 16:24 UTC; its own `gmail_snapshot_fresh` is
  FALSE. The operator should not assume silence from an incomplete inbox.
- Of the current 25 shortlisted company domains, **9 are positively
  matched to outbound history**, **15 have no positive match in the
  registry** and must remain `HISTORY_UNVERIFIED`, and **one** is an
  infrastructure/Sentry-ingestion host rather than a commercial buyer.
- Lead Smart is an existing conversation with recorded inbound reply;
  it is a **different organisation** from the Empire AI product.
- Independent founder mailbox review additionally observed earlier sent
  contact involving Abstrakt, which is not shown as positive outbound
  in the server's commercial registry. This is an evidence-reconciliation
  gap, NOT permission for another first introduction. Such externally
  observed evidence was not copied into the server as personal Gmail data.
- Existing relationship history never clears canonical suppression.
  `new_first_touch_authorized=FALSE` and
  `followup_authorized=FALSE` for every output row.
- No duplicate outreach, email sends, added Exchange inventory, funds
  movement or live production service modification.

### Next steps
- Run the next existing Gmail evidence cycle and reconcile missing
  source-domain contact history through its approved owner, retaining
  opt-outs, bounce evidence, provider provenance and suppression.
- Independently resolve stale relationship capture before preparing any
  manually reviewed follow-up drafts. Route approved buyer specifications,
  price/geo/volume and payment/fulfilment evidence to the *existing*
  canonical buyer capacity mechanism, never to a parallel side table.

### Wave 12 operational release receipt

- Full unified regression: **619 tests passed**, one existing dependency
  warning. No failed tests.
- Feature commit: `ac61871f`, clean unified agent worktree.
- Detached scheduled release:
  `/home/ubuntu/empire_worktrees/leadgen_revenue_queue_release_ac61871f`.
- Existing hourly Ubuntu cron observer retained its two runs at minute
  **23 and 53**; pinned path changed from `a0e55412` to `ac61871f` and
  `--include-contact-history` made mandatory for private materialization.
  Preserves the existing RECC and ASTRA cron entries.
- Manually verified production snapshot with new pinned code:
  `FOUNDER_RESEARCH_QUEUE_READY`, 25 domains, 9 existing contacts,
  15 history-unverified, 1 technical ingestion host excluded from
  commercial targeting, 0 send authority. Private report remains 0600
  inside a 0700 directory.
- `empire-buyer-gmail-evidence.timer`, buyer acquisition scout and
  Commercial Exchange timers all verified active; the latest Gmail
  evidence service execution returned success. The underlying mailbox
  capture reported partial/stale and **does not establish that 15 domains
  were never contacted**.
- New scheduled code **has run manually**. The next unattended cron
  execution was not yet observed at receipt time; don't equate
  an installed schedule with historical delivery.
- CRM suppression and any other mailboxes not included in the current
  relationship registry remain mandatory independent checks before
  any outbound approval. Do not automatically follow up with prior contacts.
