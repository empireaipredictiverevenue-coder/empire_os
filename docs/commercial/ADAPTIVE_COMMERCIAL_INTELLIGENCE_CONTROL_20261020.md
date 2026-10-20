# Empire AI — Adaptive Commercial Intelligence Control (v1)

Date: 20 October 2026
Worktree: `/home/ubuntu/empire_worktrees/video_commercial_framework_20261019`
Branch: `feature/video-commercial-framework-20261019`
Ownership: Commercial review adapter. Existing owner teams retain all CRM, original Conversation OS, Buyer Scout, catalog, outbound, Revenue Distribution, forecasting and payments authority.

## What was actually built

New tested modules:
- `empire_os/commercial_adaptive_intelligence_control.py`: pure evidence-contract validator; eight-node commercial causal/dependency graph; ordered review suggestions; privacy-safe, separate research cohorts; source contradiction checks; prior-report replay/dedup; source regression detection; per-gate observational memory for repeated hold, resolution and recurrence
- `scripts/review_commercial_adaptive_intelligence_20261020.py`: manual read-only composition of the **existing** sales proof reader, sales adaptive review, commercial offer-book shadow builder and Revenue Distribution shadow owner projection
- `tests/test_commercial_adaptive_intelligence_control.py`: genuine decision-contract/unit adversarial tests using synthetic TEST fixtures only
- `tests/test_commercial_adaptive_intelligence_cli.py`: full CLI replay, forged-checkpoint refusal, bounded original-source no-mutation tests using synthetic TEST fixtures only

No artificial prospect or financial entries were inserted into production. No model training, buyer activation, mail access, CRM mutation, network calls, timers, task dispatch, product pages or settlement actions.

## Live source findings (read-only)

A direct invocation against EmpireOS owner source files on 20 October 2026 returned:
- 8 **active commercial evidence gates**, not eight autonomous workers
- 255 in-memory research review targets, **not 255 purchased leads**
- 52 historical thread review cases, **not 52 authenticated inbound replies**
- 1,057 buyer capacity/source records seen, **not 1,057 verified direct buyers**
- Actual verified payments, revenue and authenticated buyer purchase events: **not established**
- Decision state: `FIRST_COMMERCIAL_INTELLIGENCE_REVIEW` / `COMMERCIAL_DEPENDENCY_EVIDENCE_HOLD`

The 8 gates:
1. `CONTACT_SUPPRESSION` — current scope, opt-out and suppression evidence from the Sales Director owner
2. `ORIGINAL_REPLY_AUTHENTICATION` — original provider event/thread, tenant contact binding from Conversation OS; only non-suppressed subcohort review may progress
3. `COMMERCIAL_SOURCE_PROVENANCE` — original producer receipts and dated first-party commercial evidence
4. `BUYER_CAPACITY_AND_TERMS` — actual buyer counterparty, buy box, accepted terms, territories and deliverability; cannot be cleared by aggregate buyer counts alone
5. `CONTACT_AND_PROSPECT_IDENTITY` — first-party exact CRM identity, dependent on original commercial source review
6. `CATALOG_DELIVERABILITY` — currently sellable and deliverable product terms, original catalog owner
7. `SEARCH_SOURCE_FRESHNESS` — Agent Web original retrieval evidence
8. `COMPETITOR_SOURCE_FRESHNESS` — original competitor source evidence

Each gate includes an existing owner, upstream prerequisites, safe parallelisation, impact expressed as **counts of research observations only**, and a list of original evidence required before it can clear.

### Precision detail: do not freeze healthy subcohorts

The 9 suppression/missing-context-held historic thread records are not the whole 52-case recovery cohort. The current engine permits evidence verification work on the other 43 independently, but does **not** permit contacting any of them without the original provider/tenant and opt-out checks. If all were suppressed/context-held, the provider-thread review node is blocked as a group.

## How it adapts from actual observations

The engine compares privacy-safe decision signatures, not emails, names, user identifiers or reply bodies.

- `FIRST_COMMERCIAL_INTELLIGENCE_REVIEW`: emit reviewed existing-owner suggestions once.
- `UNCHANGED_COMMERCIAL_HOLD`: suppress duplicate attention and avoid repeating a no-op handoff.
- `PROVENANCE_OR_METRICS_CHANGED_REVIEW_REQUIRED`: reevaluate the existing owners and show changed/cleared/newly blocked causal nodes.
- Three or more identical observations in which a gate stays active: mark it as a persistent hold. It does **not** auto-send notifications every time.
- A node that clears then returns: track a recurrence/regression. Clearing a research gate **does not** authenticate a purchaser.
- A trusted previous control report must have intact schema, digest and bounded memory matching the earlier active-gate set; unknown policy/action keys fail closed.

These are **operational learning signals**, not trained predictive performance scores. An external source receipt hash is only a source-change signal, never proof of buyer intent.

## Owner orchestrator integration contract

Pure in-process function:
```python
review_adaptive_commercial_intelligence(
    sales=current_existing_sales_adaptive_report,
    offers=current_existing_shadow_offer_review,
    distribution=current_existing_distribution_shadow_review,
    previous=previous_privacy_safe_control_or_none,
    now=timezone_aware_datetime,
)
```

Manual source-data review:
```bash
cd /home/ubuntu/empire_worktrees/video_commercial_framework_20261019
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_commercial_adaptive_intelligence_20261020 --read-only
```

Replay once an approved **existing** orchestrator has a previous safe control output:
```bash
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_commercial_adaptive_intelligence_20261020 --read-only \
  --previous-commercial-review-file /path/to/approved/previous-control.json
```

The `--previous-sales-review-file` flag can supply the Sales Director's prior adaptive review too. This branch does not persist checkpoints or register a new scheduler. After owner acceptance, **the existing orchestrator** should own secure state retention and trigger on original evidence change or its current review cycle, with explicit concurrency locks and tenant isolation.

## Next improvements (owner-backed, no duplicated agents)

- Event-triggered existing-owner source receipts and minimum-change replay with backoff (existing orchestrator).
- Original Conversation OS per-message authenticated provider receipt and exact tenant/contact ancestry, not bulk delivered-email attribution.
- Buyer-led commercial market-acceptance evidence, approved price, territory and seat capacity, not inferred from company size or visits.
- Contract/product/SKU source SLAs plus fulfilment test receipt reconciliation.
- Proper source-to-product-to-buyer knowledge graph using first-party canonical IDs and edge provenance; no fuzzy linking across tenants.
- Closed-loop value learning through the **existing Revenue OS** `assess_revenue_os_learning()` and model-review gate once independent post-decision revenue, costs, settlement and outcome receipts actually exist. No synthetic commercial feedback, no automated price or spend optimisation before that.
- Decision quality dashboard: evidence latency, owner review resolution time, false-positive holds, repeat-work avoided, true verified buyer-to-order progression, settled margin and original attribution; avoid vanity counts.
- Negative-example quarantine and policy regression tests sourced from confirmed original failures, never examples that implicitly promote a prospect to buyer.

## Verification and release

Run the full related regression suite (commercial, Sales Director, Revenue Distribution, catalog, Conversation OS, Revenue OS feedback). CLI tests use synthetic records only for *offline tests*; production-source read-only review uses existing real persisted data and makes no writes.

**Deployment boundary:** isolated branch, not merged or deployed. Existing owner review and integration approval required. No buyer send, payments or autonomous commercial authority.
