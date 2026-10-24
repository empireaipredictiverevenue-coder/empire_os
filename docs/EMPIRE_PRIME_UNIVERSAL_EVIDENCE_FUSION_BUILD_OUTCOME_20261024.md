# EMPIRE AI — PRIME Universal Evidence Fusion, original Predictive Cloud

**24 October 2026 | Isolated feature worktree; OBSERVE-only.**
Parent `813c55c5353efae230797c5bb4fff094cf5c36b9`
(`feature/prime-precision-accuracy-quality-20261024`).

## Changes in the original system

- `empire_os/prime_universal_evidence_fusion.py` is a **pure, memory-only evidence review**, not a source scraper, new engine, datastore, model or source authentication service. It defines a bounded `empire.prime.original_owner_evidence_summary.v1` interface and `empire.prime.universal_evidence_fusion.v1` aggregate output.
- `empire_os/predictive_revenue_brain_bridge.py` uses the original PRIME review and adds **one optional** `original_owner_evidence_summaries` argument, returning `prime_universal_evidence_shadow`. All existing storm, permit, CRM, original official NWS reviews, PRIME scenarios, verified-outcome shadow calibration and numerical Quant metrics remain unchanged and isolated.
- `tests/test_prime_universal_evidence_fusion.py` verifies source family coverage, owner-specific evidence classes, benign and malicious inputs, tenant isolation, over-permissioned inputs, future/stale/noncausal data, prospective prediction leakage, deduplication, correlated sources, independent links, contradictions, cross-entity links, the founder redaction boundary and no financial authority.

## Original department compatibility

The source classes map to **existing** owners, not added agent processes:
Buyer Acquisition; Smart CRM; Search Intelligence; MediaOS; Permits; Storm; Legal; Procurement; Property/Insurance; Trading/Quant; Economic Memory. Each may contribute only the constrained evidence class allocated to it. It may not manufacture a more valuable buyer or financial stage.

**All supplied receipts are claims, NOT a verified API ingestion.** Source inputs must be original-owner-provided privacy-minimised summaries after authentication, rights review, tenant access and provenance custody **outside** this pure review. A caller could forge `OWNER_REVIEWED_PERMITTED` / `ORIGINAL_OWNER_CUSTODY_REVIEWED` text; this function cannot independently validate either assertion and never reports it as verified provider authority.

The original `economic_signal_fabric.py` remains canonical for its supported OBSERVED economic signals, source/tenant identity and signal deduplication. Existing `source_intelligence_handoff.py` is an owner-controlled operational lane, not a blanket source authenticity grant. This feature does **not** route arbitrary source records through those contracts or add a new source-collection path. An original Data Cloud owner must decide and approve how to project each original validator's *approved* output into the new narrow private summary.

## Strict input contract

Exactly 18 fields: version, owner, class, SHA-256 event/origin/entity/source/tenant-scope/tenant-binding digests, observed and received UTC timestamps, source rights and provenance owner claims, permitted purpose `PRIVATE_PREDICTIVE_RESEARCH_ONLY`, up to 16 supporting and contradictory SHA-256 reference links, optional `prediction_as_of`, and `execution_authority=none`. **No raw names, addresses, email bodies, phone numbers, source payloads or customer records.** Unknown fields are rejected. Maximum 100 receipts per pure review.

- The *original reader* must create and verify hashes **after** ensuring it is permitted to access the original tenant data; matching the caller-supplied tenant hash is a consistency check, not proof of owner authentication.
- The review rejects wrong-tenant hashes, malformed or permissionless receipts, unauthorised source-owner/evidence-class combinations, future/clock-unsafe/stale receipts, lookahead predictions and trade/financial authority.
- Duplicate event digests are idempotent only if the entire private summary is byte-equivalent; conflicting revisions are quarantined. Correlated repeated publications sharing one origin hash do not increase independent source counts. Cross-entity contradiction/corroboration references are flagged as holds; missing links remain unresolved, not supportive proof.
- Founder output contains only aggregate counts, source family/class names and **local ordinal** entity-group aliases (no raw or hashed entity/tenant/source/event IDs).
- Owner-asserted evidence levels are 1 interest, 2 activity, 3 explicit enquiry, 4 commitment, 5 financial outcome. They are categorical evidence claims, **not confidence percentages**. Trading research has no commercial intent level; it is never converted to revenue labels.
- NO legitimate amount of structured input here can update the original Prime `prime_original_outcome_calibration`, `prime_prediction_quality`, revenue accounting or model promotion. Authenticated prospective prediction/outcome matching remains a separate original owner-governed process.

## Risk and release status

**Held by design:** all 11 real owner adapters are **not connected** to this new optional fusion input; the current demonstration uses tests with fabricated SHA-256 receipt fixtures. No one can call the synthetic fixtures actual replies, genuine intent, settlements, strategy profitability, verified source rights, statistically calibrated predictions, or model accuracy.

No service deployment, live ASTRA task dispatch, database connection/write/migration, Smart CRM update, buyer acquisition/mailbox change, lead outreach, media publication, financial execution, trading order, paid service, public Founder route, or automatic retraining occurred.

The Founder can consume the returned **safe aggregate object** from the existing private bridge **after original owner security/release approval**; this branch intentionally does not mount a public/private route or bypass existing Founder authentication.

### Known inherited regression blocker

The parent `813c55c...` already contains `tests/test_economic_signal_materializer.py` importing `ECONOMIC_SIGNAL_SOURCE_KEYS` from `empire_os.intelligence_materializer_transport`, where that symbol does not exist in the parent version. The broader collection fails before this feature's tests run. This inherited materializer/owner boundary was left unchanged. The remaining scoped PRIME, Quant, Economic Signal, Source Intelligence, buyer-state and predictive bridge regression modules passed **222/222** (one Starlette deprecation warning). The full broad collection was **not** clean because of the inherited materializer import failure.

### Exact original owner handoff

1. **Data Cloud + Security:** specify an original first-party authenticated, licence-checked receipt producer for *one* permitted source, including immutable origin/event, exact tenant, provenance, timestamp and revocation controls. Hash with a suitable domain-separated scoped policy approved by Security (plain SHA256 of low-entropy identities can be reversible); only approved pseudonymous digests may reach PRIME.
2. **Buyer Acquisition / Smart CRM:** independently review one genuine, permitted, tenant-scoped buyer reply/enquiry receipt; do not attach a mailbox/CRM reader here or classify industry activity as direct buying intent.
3. **Predictive Cloud / Quant / Scientific Agent:** challenge conflicting/correlated sources, prospectively register prediction time/horizon, run independent true-outcome calibration through the existing original Economic Memory pathway, and keep statistical metrics separate from asserted inputs.
4. **Core/ASTRA / Founder Auth:** reconcile exact feature changes with the dirty production checkout and approve any authenticated private summary route and rollback. No new ASTRA or economic task authority.
5. **Trading Risk Guardian:** preserve separately governed financial/trading observations; no cross-domain execution privileges.

## Reproducibility

```bash
cd /home/ubuntu/empire_worktrees/prime_universal_evidence_fusion_20261024
PYTHONPATH="$PWD" /srv/empire_os/.venv/bin/python -B -m pytest -q \
  tests/test_prime_universal_evidence_fusion.py \
  tests/test_predictive_revenue_brain_bridge.py
```

**Final authority:** `OBSERVE` | `execution_authority=none` | `no_verified_real_world_model_performance` | `no_live_source_provisioned` | `production unchanged`.

One original EmpireOS. One Predictive Cloud. One PRIME. One EmpireDB.
