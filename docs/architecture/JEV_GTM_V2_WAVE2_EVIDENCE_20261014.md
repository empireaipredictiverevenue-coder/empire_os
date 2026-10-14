# EmpireOS JEV GTM V2 — Wave 2 Engineering Evidence

Date: 2026-10-14
Owner: Revenue Intelligence / Model Evaluation
Worktree: `/home/ubuntu/empire_worktrees/jev_gtm_v2_20261014`
Branch: `feature/jev-gtm-v2-20261014`
Mode: OBSERVE; no live provider activation, no EmpireDB mutation, no outbound authority, no new worker, no timer.

## Starting point

Prior bounded release commits:
- `1645a5b7`: V2 typed multi-question contract, first-party local Choice adapter, GTM evidence composer, review queue.
- `3df027a2`: canonical CRM channel evidence and UNKNOWN suppression handling.
- The upstream main working checkout has independent work and uncommitted changes. Never overwrite, merge or deploy from the shared checkout without a separate deployment review.

## Wave 2 changes

1. **Suppression fail-closed route** — `empire_os/jev_gtm_v2.py` now routes would-be introductory/outreach candidates to `EVIDENCE_REVIEW` if canonical suppression/contact evidence is UNKNOWN. Verified existing replies still route to internal review only, never outbound.
2. **Bounded deterministic cache** — `empire_os/jev_gtm_cache.py` stores only read-only recommendation packets in process memory. Stable SHA-256 digest covers schema, policy version, exact explicit as-of timestamp, the entire input envelope including source revisions, tenant and reply content. No raw correspondence is persisted in the cache. Bounded entries/TTL, deep copy isolation, explicit event-driven invalidation and no scheduling. Caller must refresh `as_of` when replaying at a different instant. No DB schema, table, or separate cache server is created.
3. **Independent evidence buying-window summary** — `empire_os/jev_gtm_buying_window.py` distinguishes multiple observed dated signal classes from duplicated source/report references using conservative correlation groups. This is qualitative momentum, **not** purchase probability or independently proven causal source independence. Integrates into JEV output without changing decision authority.
4. **Frozen holdout challenger evaluation** — `empire_os/jev_gtm_challenger.py` consumes the existing `typed_decision_dataset` and `typed_decision_eval` owners. Enforces one frozen hash, one task, exactly matching case IDs and source lineage for incumbent/challenger, canonical labels, explicit minimum 100 cases and per-label coverage, and reports F1, confidence Brier and false-positive-interest/missed-unsubscribe risk for reply tasks. Never writes new outcomes or trains a model.
5. **Independent reviewer authenticity remains UNVERIFIED** — human review references are only strings until an authorised canonical review reader can verify their origin. Thus good offline metrics may set `offline_metrics_pass=true`, but **`promotion_evidence_review_ready=false` always** in this release and the blocker remains explicit.
6. **Unauthenticated offline export gate** — `scripts/review_jev_gtm_candidates_v2.py` cannot authenticate its local JSON source. The CLI downgrades apparent positive/outreach/followup/intro actions to `EVIDENCE_REVIEW`, marks the preview unverified, never asserts contact clearance, and returns summary statistics without raw case details by default.

## Production truth check and blockers

A privileged local aggregate query through `scripts.probe_canonical_sales_intake_aggregate_readonly` was attempted in read-only mode and was blocked by the remote tool's safety controls. No retries or bypass attempts were made. **No live canonical prospect count, reader authentication, new sales outcomes or original mailbox replies are claimed verified in Wave 2.**

The existing `empire_os.revenue_crm_suppression_evidence_reader` can return SUPPRESSED or UNKNOWN for its supported dedicated channel, and the existing CRM evidence policy declares email-channel details UNKNOWN unless separately verified. An arbitrary JSON export or search-scout result cannot transform UNKNOWN into CLEAR. Authenticated EmpireDB linkage, independent reviewer provenance and separate consent/send governance remain future gates.

## Validation acceptance

- New tests: `tests/test_jev_gtm_cache.py`, `tests/test_jev_gtm_challenger.py`, `tests/test_jev_gtm_buying_window.py`.
- Extended existing tests: `tests/test_jev_gtm_v2.py`, `tests/test_jev_gtm_review_queue_v2.py`.
- All cases with outputs are synthetic **engineering fixtures**; they are not production learning outcomes.
- Run the targeted and wider relevant suite using `/srv/empire_os/.venv/bin/python -m pytest`, with no bytecode or pytest cache writes.
- `git diff --check`, changed Python compile, independent isolated commit, worktree clean.

## What remains before full 12-capability programme closure

- An independently authorized, exact-tenant EmpireDB reader for real canonical prospects, relationship links, reply linkage and channel evidence; tests must prove its own role, tenant and row-level boundaries.
- Real independently reviewed datasets with authenticated label provenance, true holdout isolation and drift monitoring; outcome-based calibration must beat baseline.
- Deployable local Score/Noul inference implementation only after real compatibility tests; the existing Laya batch adapter supports **Choice** only.
- Reproducible buyer-window performance against observed buying cycles, cohort-specific policies and value-of-information economics; no invented probabilities or guaranteed sales claims.
- Founder-facing CRM integration, approved policy promotion and production gauntlet; live outbound permissions, contracts and funds remain under existing controls.
- If paid inference is later considered, compare it against sovereign inference and separately authorize cost.

## Success criteria

No duplicate infrastructure. No source data promoted beyond its provenance. No artificial contact permission. No synthetic commercial claims. Deterministic replay. No automatic emails, calls, funds, production database writes or scheduling. Evidence-backed completion only.
