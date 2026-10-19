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
