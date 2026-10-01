# Revenue readiness completion delta — 2026-09-29

Diagram: existing acquisition timer → run_acquisition_cycle → crawler_runner →
canonical EmpireDB ingestion / Signal Fabric inbox → acquisition/latest.json →
Revenue Distribution. OBSERVE crawler probes must write neither store.
Canonical BuyerAllocationDataRepository → buyer_activation_decision and shared
identity-quality classification → Buyer Capacity → Revenue Distribution.
BuyerDiscoveryRepository / CanonicalBuyerRecoveryRepository remain the discovery
and recovery readers; discovery and replies cannot establish commercial gates.

Owner: existing acquisition and buyer allocation components, Phase 4 OBSERVE.
Worker assignment: Codex owns this bounded delta; focused tests and separate
post-change contract inspection provide verification. Preserve concurrent work.
No new service, database, crawler, role, authority or commercial writer.

Changes: repair dry-run signal enqueue; classify obvious test/noise and explicitly
non-buyer identities for review hold; distinguish unreviewed discovery, reviewed
unknown terms, and recorded verified terms using existing canonical fields.
Classification is a conservative review projection, never proof of identity or
permission to activate. Existing activation decision and every commercial gate
remain mandatory. Capacity metrics exclude identities held by the classifier.
Reserved test endpoints require a hold, even if activation fields are populated.

Truth: EmpireDB rows are canonical. Runtime artifacts are dated observations,
not a replacement database. Never reconstruct the 1057 rows from aggregate counts.
A live database audit cannot complete without the authorized runtime connection.
Lead Smart source-referenced review remains unverified commercial terms; affiliate
approval does not establish payout, geography, capacity or routing. No Connex
relationship may be inferred from a name/search hit. Outreach is not a reply.

Execution: pure deterministic projections, existing bounded source runner and
atomic snapshot refresh. Dependency failures preserve last-known-good artifacts;
no refreshing source timestamps or substituting cached success for current failure.
Rollback: reverse only this task's scoped edits; no database mutation to reverse.
Verification: crawler signal/prospect no-write tests, identity hold and activation
regressions, discovery/recovery/capacity/allocation/gateway/distribution tests,
compilation, diff checks, protected hashes, then safe OBSERVE artifact refreshes.
Production completion requires live canonical classification; report access limits
rather than claiming that passing local tests meets that requirement.


## Verification and evidence record

317 focused/adjacent tests passed. Twelve changed Python files compiled.
Whole-worktree `git diff --check` passed. One additional test module,
`tests/test_buyer_discovery_preview.py`, has a pre-existing collection failure:
its import of `_load_env` from `scripts.buyer_discovery_preview` is unresolved.
Neither file was changed. The passing run excludes that module. No full-suite
claim is made. Scoped before/after diff inspected independently of inherited diff.

Crawler root path: Revenue Distribution SOURCES.crawler → acquisition/latest.json
→ run_acquisition_cycle → crawler_runner → CrawlerProspectRepository / Signal
Fabric inbox. Installed `/etc/systemd/system/empire-acquisition.service` lacks
`/etc/empiredb.env`; the already-dirty repository unit includes it. Latest observed
Overpass failure (19:55:56 UTC) reports the EmpireDB provider unconfigured. Systemd
bus is inaccessible and protected environment files are unreadable in this session.
The missing DSN is a runtime provisioning/deployment blocker, not permission to
substitute legacy access. No installed unit was changed or restarted.

Additional corrected defects: dry-run signal enqueue, CourtListener obsolete
root-home token lookup, and all-failed CourtListener queries reported as successful
empty acquisition. New OBSERVE probe failed closed with no successful external
query, zero candidates/accepted and one source error. It used a separate temporary
log and did not overwrite acquisition latest/last_success or enqueue any signal.
Scheduled CourtListener success at 20:07 UTC is corroborated by the existing
Signal Fabric inbox (120 CourtListener records total, most recent last_seen_at
20:07:00 UTC). These are unresolved signals, not canonical prospects or supply.
Latest scheduled snapshot at 20:11:50 UTC: NYC HPD, ok=true, returncode=0,
prospect_acquired=false, signal_queued=false. No manual ingestion was run.

Safe Revenue Distribution rebuild: 21 opportunities / 29 proposal-only actions.
Only blocker: acquisition_budget_unknown:zero_cash_planning. All authority flags
remain false. Crawler unavailable is cleared by the genuinely fresh scheduled
artifact; no source timestamp was edited and no old success substituted for failure.

Buyer Capacity refresh attempted and failed with DataGatewayUnavailable; previous
snapshot remained byte-identical. Discovery and recovery canonical reader factories
also fail closed. Thus 1057 buyer rows are NOT individually audited in this session,
and genuine/discovery/test/non-buyer counts across those rows remain UNKNOWN.
Last verified snapshot remains reviewed=1, terms_verified=0, capacity_verified=0,
delivery_verified=0, fully_activated=0, allocation_ready=false. New identity quality
classifications are implemented/tested but their live counts remain unavailable.

Accessible evidence inventory (different populations; do not add these counts):
- One Lead Smart REVIEW_ONLY artifact with source reference
  gmail:1a0d9ce883c87d4a:buyer_requirements_2026-09-25. It records supply requirements;
  payout/currency/geographies/capacity/RTB terms remain unknown. Original reply
  content was not accessible. Affiliate approval context is recorded separately in
  docs/LEAD_SMART_EVIDENCE_DELTA.md and is not verified commercial terms here.
- No Connex evidence located in inspected readable buyer/revenue/conversation/
  enterprise artifacts. This is unknown, not proof of absence from EmpireDB.
- Buyer-state artifact dated 2026-09-22 has two linked entities in READY/RESEARCHED
  states; all conversation and downstream commercial states are unknown.
- Scout review-readiness artifact: 46 candidates, two review-ready, 44 blocked.
  Review readiness does not establish buyer relationship, terms or capacity.
- Enterprise activation artifact: nine canonical prospects reported, nine qualified,
  two verified person contacts and two review-ready. No outreach authorized.
- Conversation recovery artifact dated 2026-09-28 reports 40 delivered first touches,
  37 followup-eligible and three suppressed after delivery. Delivery is not a reply,
  interest, payment or terms. No messages were sent or proposed by this task.

Evidence was materialized in this review record only; no buyer row, commercial
ledger, review approval or verification timestamp was mutated. No payout, geography,
capacity, delivery route or commercial relationship was invented.

Checklist: diagram/delta and worker assignment done; code, negative/recovery tests,
compile, diff inspection and protected hashes done; OBSERVE Distribution refresh
done. Live canonical ingestion, 1057-row audit and classification, buyer evidence
join/materialization and Buyer Capacity refresh remain BLOCKED by runtime access.
Founder/host operator must deploy the prepared environment configuration through
the approved service process; any restart/live ingestion requires separate approval.
External buyers must supply verifiable terms, capacity and delivery evidence before
existing activation gates may pass. No production-completion claim is made.

Protected SHA256 values unchanged:
- Predictive Revenue: ed258882dd71a4292fea670807f5e5a451cdc4482f2da2204d5f6a2293e5bc2e
- Predictive Cloud: ccbb9b49c31bd4aca57e9d5312de034d20624f3db0344ab0cffed8ed1b99c406
- Migration 018: e7edcfe1d0f94c3898437e68db0714557370b7b86f9b21ee76cc04be60bc3c21

Task-scoped files (pre-existing changes retained):
- `empire_os/buyer_allocation.py`
- `empire_os/buyer_capacity_readiness.py`
- `empire_os/crawler_runner.py`
- `tests/test_buyer_capacity_readiness.py`
- `tests/test_crawler_runner.py`
- `empire_os/lead_sources/court_listener.py`
- `empire_os/canonical_data_gateway.py`
- `empire_os/buyer_discovery_repository.py`
- `empire_os/buyer_recovery_repository.py`
- `scripts/build_buyer_capacity_readiness.py`
- `tests/test_buyer_allocation_repository.py`
- `tests/test_revenue_readiness_boundaries.py`
- `docs/architecture/revenue_readiness_completion_2026_09_29.md`

Observed artifact hashes at recording time (scheduled writers may advance):
- `runtime/revenue/lead_smart/roofing_pilot_review.json` SHA256 `78ff11b29daaa038d7709c17d32e77e6edb7b51b060c148bd001bf62096b03af`
- `runtime/buyer_state/buyer_state_latest.json` SHA256 `3e69bdb71d0228a8162d9c6ab65b2ddfdea8290482dedb4f9021cf145532c027`
- `runtime/buyer_acquisition/review_readiness_latest.json` SHA256 `98d2ffb20bdcff65a7317634b7a0901a11d440692c1568fb21ceb08c88c21c43`
- `runtime/predictive_revenue/enterprise_activation_latest.json` SHA256 `840b95b00bc8f201d3097e72d57cf4ef768acd4e944b00649d21c2fa39fd540b`
- `runtime/conversation_recovery/latest.json` SHA256 `e275f7eaded2fed7963b30828333b451f0cf2e26733877d14a013ff236964fae`
- `runtime/buyer_capacity_readiness/latest.json` SHA256 `5c46f682fa7ad72847966b06848571a3a6b15bfb79c6e393e8bb99e19e5d5066`
- `runtime/acquisition/latest.json` SHA256 `ccc2cabb3ad5796587f0312883febb00870a70287085a0e99c18c30b7a05c8de`
- `runtime/acquisition/last_success.json` SHA256 `8e03a43b0412b7b1b6d946e420fb6a263804c5c4819937e7cb9b7499dc9821c4`
- `runtime/revenue_distribution/latest.json` SHA256 `0a41d0509b5e7ea41adc7535c4dd04f6d5cb5f13aebc4f5614a374ff833210e1`
