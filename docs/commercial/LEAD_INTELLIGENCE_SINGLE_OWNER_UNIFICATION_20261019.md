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
