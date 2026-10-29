# Empire AI — automated buyer evidence recovery and founder action desk

**13 October 2026 · OBSERVE · isolated and committed source candidate, not production loaded**

## Why this is the minimal integration
EmpireOS already has the authorised 30-minute buyer acquisition scout, buyer-network first-party site and due-diligence refresh, buyer qualification queue, enterprise contact sync, 2-minute deferred enrichment worker, founder review materialisation, reply reconciliation and Outbound Governor. Creating another scheduler, agent, CRM, database or external provider would duplicate the operating architecture and undermine first-party truth.

The current 2,136-record deferred queue had 2,051 candidates that the proposed evidence parking policy would hold without new evidence. Repeated unsuccessful probes have sometimes exceeded 1,000 attempts. The previously implemented isolated patch (commit `f40e8f6b`) prevents routine retries on evidence-exhausted records and preserves the ability for distinct same-host named-person or newly verified company contact-route evidence to wake a prospect, including when a worker held a lease. The canonical production queue has NOT been altered.

## Automatically performed after the buyer scout completes
The existing `scripts/run_buyer_acquisition_scout.py` invokes `scripts/run_buyer_network_evidence_cycle.py` within its current 30-minute schedule. The bounded read-only pipeline now adds a fourth and final stage:
1. Existing bounded first-party direct-site probe.
2. Existing first-party due diligence.
3. Existing private founder qualification action refresh.
4. NEW `scripts/build_buyer_recovery_action_desk.py --write --repo-root /srv/empire_os`: deterministic snapshot-to-founder-action triage.

The new stage reuses the durable `runtime/hunter/buyer_deferred_enrichment.json` and the existing queue's same-host evidence and retry-lane contracts. It does not crawl, requeue, claim work, refresh CRM contacts, send email, access secrets, change EmpireDB, call an external API, sign a contract, activate traffic, or move funds.

The packet is a private `0600` atomically written file:
`runtime/buyer_network_intelligence/buyer_recovery_action_desk_latest.json`.

Each high-priority research item contains: canonical prospect ID, business/domain, commercial priority, existing product hypothesis (NOT product readiness or buyer demand), retry/parking status, existing same-host person-evidence URLs to reverify (NOT a validated email), verified company-route *types* (no contact values), missing evidence and exact next research action. This is not an automatic sender list. The report is capped at 25 detailed rows with truthful full-population totals and truncated-report indicator. Two rows sharing a domain remain separate identities and their duplicates are called out, not merged.

The full source JSON is bounded, schema-checked and SHA-256 pinned across the analysis; concurrent source mutation fails closed. A source symlink, malformed/oversize data, or unsafe report destination blocks emission. No raw email contact values or secrets appear in the report or console output. The prior zero-authority commercial gates remain unchanged.

## Read-only test evidence
- 94 scoped tests passed, including 41 directly affected tests; tests cover source/identity integrity, false same-host claims, source symlink rejection, private output, loop safety, no outbound, duplicate domains, priority ranking, and worker lease / fresh-evidence wake.
- Production-source **read-only** report projected 131 high-priority records and 2,051 eligible for parked-policy status. Top product-matched candidates included Neighborly, TurnPoint, EQT, Blackstone Operating Team, Vista Equity Partners, Authority Brands and Apex Service Partners. These are still unqualified research targets.
- An isolated temporary-directory `--write` produced the packet with mode `0600`, and the canonical source JSON hash was unchanged. A production-path run without `--write` also retained the same queue SHA-256. Production output path was not created.
- This is code/test/isolated-source evidence; **NOT a claim of live automatic execution**.

## What remains outside permitted automatic authority
- The first-party professional `phil@mail.empire-ai.co.uk` / `reply@mail.empire-ai.co.uk` IMAP/SMTP credentials and sender configuration are not yet proved in production. Gmail connector activity in ChatGPT is not a first-party live inbox connection on the server.
- Nineteen October 13 Gmail send IDs were confirmed in Gmail but are NOT canonical EmpireDB outbound intentions by virtue of this report. No repeat sending without an exact live history and suppression check. The four older hard-bounce/block recipients remain no-retry pending controlled suppression reconciliation.
- Buyer appetite, procurement authority, exact person-bound contact, lawful purpose/source, commercial price/terms, signed agreement, funds, live USDT BSC settlement, fulfilment and revenue reconciliation remain separate.
- Fully self-sending outreach should only be enabled after the founder separately approves a **bounded standing policy** with explicit permitted persona, source, daily cap, domain exclusion/suppression, human escalation, owned transport, country/compliance and kill switch; this release does not grant such approval.

## Controlled release handoff
1. Review isolated branch `feature/buyer-evidence-park-20261013` commits. Do not overwrite the dirty production main checkout or other specialist worktrees.
2. Under separate exact release authority, reconcile/merge the bounded source + tests into the live main branch and run its scoped production-source regression.
3. Only under explicit activation/restart approval, load the updated source in the existing 2-minute enrichment service and existing buyer scout cycle. Do **not** create another timer or restart unrelated services.
4. Read back generated packet's schema/version, source hash, owner/mode `0600`, exact research counts and source/worker effects; prove NO sends/calls/payment.
5. Next independent revenue milestone: verify one person-bound, willing buyer and a product-specific scoped pilot; founder approves actual commercial send/terms/payment under the established gated loop.

**Status:** RESEARCH_AUTOMATION_CODE_COMPLETE / TESTED / NOT_PRODUCTION_ACTIVE.

## Production acceptance — 13 October 2026 (supersedes earlier pre-release status)

**Release status: ACTIVE FOR FIRST-PARTY BUYER RESEARCH / OBSERVE ONLY.**
This section documents a later completed activation; the preceding preparation
notes are retained as pre-release evidence, not the current deployment state.

- Existing production branch `agent/data-cloud-wave4`: commit `302f8b1f`
  installed bounded evidence-parked buyer queue and the existing scout's
  fourth research/review stage. Commit `24fc1553` made zero-valued telemetry
  explicit. Commit `df9f70f5` aligned the existing revenue supervisor.
- Existing acquisition-scout and deferred-enrichment timers remained **active**.
  Existing revenue-completion-supervisor timer also remained **active**.
  No new agents, queues, timers, services, migrations or service restarts.
- An operator-authorised, bounded production OBSERVE cycle completed at
  `2026-10-13T11:42:04Z`:
  direct-site probe PASS, first-party due diligence PASS, founder-qualification
  actions PASS, and buyer recovery desk PASS.
  Its durable evidence is
  `runtime/buyer_network_intelligence/research_cycle_latest.json`.
- The private `0600` first-party report
  `runtime/buyer_network_intelligence/buyer_recovery_action_desk_latest.json`
  contains 131 high-priority candidates (25 detailed review cases), 2,051
  evidence-exhausted records to park, and **zero currently due**. The
  shortlist includes product-scoped enterprise hypotheses but no recipient
  has been admitted to outbound authority solely from this list.
- The existing 2-minute revenue supervisor was independently read back at
  `2026-10-13T11:46:52Z` with `due_now=0`,
  `evidence_parked_count=2051`, `high_priority_parked_count=125`,
  `genuine_review_ready_count=0`, and
  `next_action=await_automatic_first_party_evidence_refresh`.
  The historical backlog still reports CRITICAL: parking an item does not
  fabricate completion, verified buyers or revenue.
- Final targeted production regression: **120 tests passed**. A pre-existing
  modified test file and the wider 63 tracked changes in the main checkout
  were preserved; staging covered only audited release paths.

### Remaining hard gates — not part of this OBSERVE activation

1. **Owned professional mailbox:** independently checked live Founder API
   returned `provider=owned_imap`, `configured=false`,
   `status=CONFIGURATION_REQUIRED`. The protected owned IMAP credential file
   was absent. Do not invent a host or password, silently use private Gmail,
   change MX, turn on SMTP, or claim owned-mailbox reply ingestion.
2. **No duplicate sends:** the 19 October 13 Gmail messages verified in the
   connected personal mailbox must be reconciled with canonical EmpireDB
   evidence before any automated outreach. Hard bounces/blocked recipients
   remain explicit do-not-retry review holds. Do not treat one-way sends as
   interested replies.
3. **No automatic commercial execution:** exact recipient, person-bound
   identity, jurisdiction, consent/suppression, offer/fulfilment readiness,
   sender reputation, human/standing founder approvals, binding terms, USDT
   settlement and genuine realised revenue evidence are separate gates.
   No automatic email, telephony, consumer calls, live Ringba traffic,
   purchasing, signatures, or payments were authorised by this release.
4. **No fabricated advancement:** `genuine_review_ready_count=0`; the
   automatic desk prepares evidence and prioritises research only.
   A positive buyer reply must be authenticated and admitted through the
   established commercial/identity pipeline before the next sales step.

**Operational conclusion:** Repetitive buyer evidence prioritisation,
bounded retries, scheduled first-party qualification and private founder
review-packet refresh are now integrated into the existing EmpireOS runtime.
Full hands-free outbound and closing remain separately blocked by the
unprovisioned owned mailbox and commercial/identity gates.

## Current operational evidence continuity checkpoint — 29 October 2026 (founder voice review)

**Scope / owner:** Original Commercial Exchange, Search Fabric, Buyer Acquisition and qualification owners; this is a cross-owner *read-only audit finding*, not a production release or an instruction to take over another worktree. Current branch `agent/data-cloud-wave4`; production checkout has many concurrent edits. Preserve all owner files and current release controls.

**What was already completed and must not be erased:**
- Search Fabric's source evidence memory: `runtime/search_fabric_evidence/source_evidence_catalog_v61.json` held **4,859 distinct prospects observed** (29 Oct, 12:24 UTC), including 269 first-party name-only and 746 first-party name+phone corroboration observations; 2,473 rights/robots holds; none of these alone is verified commercial contact permission.
- `runtime/search_fabric_evidence/canonical_review_sync_v63.json` reports **4,847 successful inserts**, status `CANONICAL_REVIEW_SYNC_CURRENT`. These are review-only observations appended to `public.search_fabric_site_observations_v62` by `empire_os/search_fabric/canonical_review_evidence_v62.py`, **not prospect identity-link or buyer approval**.
- Existing qualification, prospect-recovery and Exchange machinery is running. The protected 15-minute prospect recovery supervisor receipt `/var/lib/empire-prospect-recovery-agent/latest.json` (12:26 UTC) reports **33,894** canonical prospects, **33,894 v2 records**, **3,659 v2-scored**, 1,408 hot and 1,396 warm. A v2 record is NOT equivalent to a scored, identity-ready, saleable or revenue-producing prospect.
- Earlier qualified/identity-ready/score observations cannot be declared deleted based on a later zero in a **different 200-row selection**; compare exact prospect IDs and selection predicates before asserting loss.

**Verified breakpoints (29 Oct snapshot):**
1. `scripts/refresh_commercial_exchange.py` selects the top **200** v2 **scored** hot/warm evidence-confidence candidates first, then fetches `prospect_entity_links` where `active=true` **only for those same IDs**. At 12:30 UTC the snapshot reports `identity_links_available=0`, `omega_scoring.scores_with_exact_qualification_and_identity=0`, and 200 blocked for missing active identity; these are *window-scoped* counts, not the full 33,894.
2. Commercial Exchange's projection does **not directly read** `public.search_fabric_site_observations_v62` in its present refresh path. Existing research evidence therefore remains distinct from the identity/qualification join needed for Exchange; no implied right to auto-promote it. Trace evidence IDs through existing owner admission workflow and identify any missed *valid* verified-link transfer rather than discarding or re-researching data.
3. `runtime/buyer_acquisition/review_readiness_latest.json` (12:01 UTC) reports 200 held and 0 review-ready: 89 missing direct buyer evidence, 69 low site evidence, 26 registry mismatches, 13 territory unverifiable, 3 incomplete business identity. This is the **separate Buyer Scout cohort**, not the 200 Exchange prospects.
4. Original `scripts/build_buyer_recovery_action_desk.py` read-only execution PASS (29 Oct) found **137 high priority**, **25 detailed review packets**, **2,155 parked**, and flagged `STALE_SOURCE_REBUILD_REQUIRED`. Existing research cycle and data quality require owner diagnosis; no outbound was sent.
5. The original prospect recovery agent supervises existing workers and reports no qualified buyer/verified sale; it does NOT repair cross-system evidence admission. One cycle selecting zero fresh websites is not proof the archived 4,859 observations disappeared.

**Highest-value next original-owner action:** Implement and independently test an exact-ID read-only **evidence continuity/reconciliation** between the V62 archived site observation, original verified identity/qualification records, current Exchange selected IDs and Buyer Scout direct-purchase evidence. Publish counts: existing evidence found; accepted; stale/rights-held; eligible but omitted; selected with/without active identity; rejected with exact reason; already processed. Investigate selection bias/starvation, avoid re-probing unchanged sources and preserve source lineage. Then repair any verified missing handoff through the EXISTING owner workflow under its ordinary execution policy. Jev can prioritise **remaining unknowns**, but cannot invent identity, buyer intent, source rights or permission.

**Authority/outcome:** Evidence audit only. No new worker, database, queue, model/provider call, outreach, production deployment, funds, live trading, permission expansion or revenue recognition was authorised or performed by this checkpoint. The founder's priority-100 durable directive is `directive_1b308d104e804c55b610125425930eca`, original planning job `coder_job_2b291bfbdcd94e7ab54e0cc61012e4fe` completed and the directive is `implementation_ready`, NOT deployed.

**Exact-ID snapshot join, 29 October 2026:** Compared 200 unique Commercial Exchange inventory prospect IDs with Search Fabric's 4,859 archived prospect IDs using existing local JSON only (no database, network, or production mutation). **126 of 200 exact IDs overlap**; 74 of 200 lack a matching archive entry.
Of those 126 archived IDs: 39 show FIRST_PARTY_NAME_AND_PHONE_OBSERVED_REVIEW_ONLY, 2 show FIRST_PARTY_BUSINESS_NAME_OBSERVED_REVIEW_ONLY, 30 show FIRST_PARTY_NAME_NOT_CORROBORATED, and 55 show SOURCE_RIGHTS_OR_ROBOTS_HOLD.
**41 exact matched prospect IDs have first-party business-name corroboration (39 also phone evidence), but zero independently verified legal identities and zero verified contact permissions in this archive.** The Exchange current 200-record snapshot separately reports zero active identity links.
**Owner next action:** Trace those 41 exact UUIDs through existing source-observation admission, independent company identity checks, and the active prospect_entity_links join. Investigate 74 evidence-absent Exchange IDs separately, without re-probing the other 126 unchanged sources. No identity verification, outreach authority, money movement, production deployment, or repaired handoff is claimed here.

**Historical-vs-current preservation, 29 October 2026:** Pinned original 26 October v51/v55 read-only records under /home/ubuntu/empire_research/osm_geofabrik_texas_20261026 recorded **12,330 active entity-linked prospects** across 33,653 prospects, **266 linked v2-scored** and **116 linked hot/warm at evidence floor**. This is historical, not proof those exact counts remain current. The current 29 October Exchange reports zero links **within its top 200 v2 hot/warm confidence-ranked selection**. The code in scripts/refresh_commercial_exchange.py fetch_qualified_candidate_ids() applies LIMIT 200 **before** fetch_identity_map() joins active links, so linked candidates outside that window may be invisible. Independently reconcile current eligible+linked intersection across the whole pool before changing ranking, rather than treating a 200-sample zero as zero overall or auto-promoting source-site observations. Any correction must retain exact prospect UUIDs, verified identity, deterministic ranking and existing buyer/rights/consent gates. Source-join diagnosis remains unshipped.

**Isolated engineering correction staged, 29 October 2026:** Branch feature/exchange-linked-selection-20261029, worktree /home/ubuntu/empire_agents/exchange_linked_selection_20261029, commit 5836f28fa. Scope: scripts/refresh_commercial_exchange.py and tests/test_refresh_commercial_exchange_empiredb.py.
New optional CLI --prefer-verified-identity: scan up to 3,000 independently scored hot/warm v2 candidates in batches of 500; prefer only candidates with a single already-active, unambiguous identity link, and fill remaining slots from the original qualified selection. The default production mode is unchanged. Search Fabric site observations do not create or authorize identity links. Existing rights, contact, buyer and payment gates are unchanged.
Proof: 59 scoped regression tests passed, compileall and git diff --check passed. New tests reproduce qualified-linked candidate stranded outside top window and prevent priority promotion of an ambiguous link.
Release status: BUILT AND TESTED, NOT LIVE. Original Commercial Exchange owner must first verify exact canonical full-pool eligible-linked counts and the candidate-delta against current EmpireDB, then use existing guarded release. Do not infer verified buyer capacity or saleable inventory, and do not create another service or timer.

## Founder live EmpireDB proof — 29 October 2026

The founder ran the existing exact read-only 20261029 Exchange SQL from isolated branch `feature/exchange-linked-selection-20261029`. Its single aggregate result: qualified full pool **2805**, exactly-one-active-link **153**, ambiguous **0**, top-200 qualified **200**, top-200 linked **0**, linked outside top-200 **153**. Transaction explicitly ended `ROLLBACK`.

This establishes **ranking-window starvation**: all 153 already active-linked qualified prospects are excluded by the current highest-score-first 200 candidate window. Historical identity evidence is not missing. It does not verify resale rights, compliant contact, buyer capacity or payment readiness.

Existing source fix `5836f28fa` and diagnostic `ee26fad11` add optional `--prefer-verified-identity`; 59 existing regression tests passed again on 29 Oct. Branch stays isolated; **production not activated**. Original Commercial Exchange owner should run a source-matched protected full candidate preview, independently check its selected IDs and downstream eligibility, integrate through its existing guarded release, verify production readback and rollback. No direct site evidence to identity auto-promotion or new scheduler.
