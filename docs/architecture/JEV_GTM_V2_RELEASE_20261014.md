# EmpireOS JEV GTM V2 — Isolated Engineering Release

Date: 2026-10-14
Branch: `feature/jev-gtm-v2-20261014`
Worktree: `/home/ubuntu/empire_worktrees/jev_gtm_v2_20261014`
Base commit: `fdce9356`
Mode: OBSERVE / zero production activation
Purpose: Revenue-first, multi-question decision intelligence without duplicating existing EmpireOS commercial owners.

## 1. Existing contracts reused

- `empire_os.icp_buyer_trigger_intelligence.assess_icp_candidate` owns heuristic ICP assessments.
- `empire_os.buyer_reply_operations_agent.analyze_buyer_reply` owns deterministic reply triage and preserves opt-outs.
- `empire_os.predictive_revenue_jev.compile_predictive_revenue_jev` and Quant Brain own economic recommendations. GTM V2 **consumes** their already-compiled, verified-scope packet; it never invents a revenue probability or recalculates a commercial model.
- `empire_os.laya_http_provider.LayaHttpTypedDecisionProvider` owns the first-party Laya shadow transport.
- `empire_os.typed_decision_store`, `typed_decision_eval`, `typed_decision_readiness` remain canonical evaluation and append-only persistence owners. No new database or store was created.
- `empire_os.revenue_crm_channel_evidence.review_channel_evidence` remains the channel evidence authority. The new adapter consumes its typed result; it does not override its consent/suppression decisions.
- Existing suppression/consent and outbound governor remain authoritative. GTM V2 is not an alternative suppression processor.
- This release does not create a scheduler, worker, new agent runtime, mailbox, API subscription, database role or paid service.

## 2. What is implemented

### Multi-primitive decision contracts
`empire_os/typed_decision_batch.py`
- Versioned `DecisionQuestionV2`, `DecisionBatchRequestV2`, `DecisionBatchResultV2`.
- Choice: bounded label sets, optional normalized distributions.
- Score: explicit min/max, finite numeric score.
- Noul: true/false criteria and bounded finite probability.
- Explicit identity, schema, provider lineage, per-question validation and no-execution invariants.
- An output schema is not an inference capability. Score and Noul require a separately validated compatible provider or observed deterministic source.

### First-party local batch adapter
`empire_os/laya_http_provider.py`
- New `evaluate_batch` sends multiple Choice questions against a single shared state to existing local `/v1/systemone`.
- Rejects Score and Noul from this adapter until real sidecar compatibility is verified, without making an external request or fabricating model values.
- Validates provider replies and retains both class probability distribution and model-reported confidence as *different* quantities.
- Always shadow-only. Does not replace the backward-compatible existing single-question interface.
- A live local test with two synthetic Choice questions succeeded. Confidence scores **must not** be interpreted as sales probabilities.

### GTM evidence and decision composer
`empire_os/jev_gtm_v2.py`
- Consumes first-party canonical, independently verified identity and tenant binding.
- Accepts timestamped, source-backed OBSERVED signals only; excludes stale, future, missing, duplicate and cross-entity/cross-tenant evidence.
- Rejects scope-mismatched or authority-bearing economic packets.
- Uses existing deterministic ICP and reply code.
- Requires same-entity, same-tenant person identity and time-bounded relationship provenance for warm-introduction review.
- Requires independently linked reply thread, matching entity/tenant and timestamp before classifying it as a relevant customer response.
- Preserves suppression priority, abstention/review on contradictions, evidence gaps and unverified reply linkage.
- Suppression readback is treated as verified only with canonical provenance, exact state and reference. The current CRM suppression-hit-only reader cannot prove CLEAR; its UNKNOWN state is never promoted to clearance. The fictional input fixture illustrates a future trusted clearance reader and must not be applied to existing UNKNOWN outputs.
- Creates reproducible hashed decision fingerprint sensitive to signals, reply text, relationship and source revisions.
- Never returns a fabricated purchase probability, revenue fact, value-of-information estimate, contact approval or outbound action.

### Existing CRM suppression-evidence integration
`empire_os/jev_gtm_channel_evidence.py`
- Invokes the existing `review_channel_evidence` policy owner using typed `TrustedChannelEvidence`.
- The existing email-channel reader returns UNKNOWN, not clearance. UNKNOWN is never mapped to CLEAR.
- A verified suppression hit, opt-out or CRM hold blocks review; a trusted full clearance proof still does not authorise outbound.
- Does not create a new suppression reader, database function, send path or consent policy.

### Tenant-scoped review queue / offline CLI
`build_jev_gtm_review_queue` and `scripts/review_jev_gtm_candidates_v2.py`
- Exact tenant binding on every case and rejection of mixed-tenant/duplicate opportunity batches.
- Bounded batch size.
- Ranked internal review: real replies > warm introductions > later follow-ups > other suggested outreach > research/hold.
- Canonical positive economic evidence is only a tiebreaker within the same action class.
- JSON command takes an explicitly provided local dataset; does not search disks, query DB, send mail, log raw reply bodies or write a file.
- Default CLI returns an aggregate summary; detailed evidence is optional with `--include-items`.

## 3. Required input example (fictional)

```json
{
  "cases": [
    {
      "account": {
        "entity_id": "ent:demo",
        "tenant_id": "tenant:demo",
        "opportunity_key": "op:demo",
        "entity_verified": true,
        "tenant_binding_verified": true,
        "description": "roofing contractor hiring for expansion",
        "target_buyer_pools": ["local_and_smb_buyers"],
        "target_product_codes": ["managed_service"],
        "first_party_people": [{"title": "owner"}]
      },
      "signals": [
        {
          "signal_id": "signal:demo",
          "entity_id": "ent:demo",
          "tenant_id": "tenant:demo",
          "signal_type": "hiring",
          "source_id": "source:demo",
          "truth_class": "OBSERVED",
          "observed_at": "2026-10-14T09:00:00+00:00",
          "evidence_refs": ["source:demo:page"]
        }
      ],
      "outreach": {
        "suppression_checked": true,
        "suppression_state": "CLEAR",
        "canonical_readback_verified": true,
        "suppression_readback_ref": "proof:demo"
      }
    }
  ]
}
```

Operator can run a **read-only** review against an authorised export; the `tenant-id` must come from a trusted source, not a user's claimed identifier. Example:

```sh
cd /home/ubuntu/empire_worktrees/jev_gtm_v2_20261014
/srv/empire_os/.venv/bin/python -m scripts.review_jev_gtm_candidates_v2 \
  --input /path/to/authorised/tenant-export.json \
  --tenant-id tenant:demo \
  --as-of 2026-10-14T09:00:00+00:00
```

DO NOT infer live readiness from synthetic example records. Canonical reader integration needs its own approval and proof.

## 4. Hard invariants

1. No outbound sending, calls, follow-up creation, suppression mutation, canonical data writing, settlement, payment, fulfilment or recognized revenue.
2. Company and tenant identity cannot be inferred from arbitrary caller text. Supply provenance only from an authorised canonical reader.
3. Never promote model claims over verified commercial evidence. Outbound governor and founder approval remain separate.
4. Every commercial opportunity is review-only; `outbound_approved=false`, `contact_permission_granted=false`, `actual_revenue=false`, `execution_authority=none`.
5. Hosted Jev/TypeSafe subscriptions and new runtimes are not required or activated.
6. No automatic task scheduling. Invoke through the existing governed orchestration only when explicitly enabled.
7. Do not confuse confidence of correct classification with class probability, conversion likelihood or economic value.

## 5. Validation

Run after changes:

```sh
PYTHONDONTWRITEBYTECODE=1 /srv/empire_os/.venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_jev_gtm_v2.py tests/test_jev_gtm_review_queue_v2.py \
  tests/test_jev_gtm_channel_evidence.py tests/test_laya_http_batch_v2.py tests/test_laya_http_provider.py \
  tests/test_typed_decision_provider.py tests/test_buyer_reply_operations_agent.py \
  tests/test_predictive_revenue_jev.py
```

Tests include deterministic replay, opt-outs, unlinked replies, cross-tenant signal/reply checks, wrong identity, stale/future/duplicate evidence, contradictions, quant provenance/negative margin, invalid distribution, Score/Noul validation, wrong native provider capabilities and CLI isolation.

## 6. Programme enhancements and activation boundaries

**Completed for this release:** multi-question decision contracts; first-party Choice batch; evidence-first GTM recommendation; reply recovery prioritization; source-scope/freshness/contradiction checks; relationship introduction reviews; canonical modeled economics consumption; reproducible fingerprint; tenant-scoped prioritized review queue; no-side-effect local CLI and tests.

**Separate engineering deliverables still required for the complete 12-enhancement programme:**
- Read-only adapter from authenticated EmpireDB canonical prospects, existing mail/reply and relationship registries into V2 input (inspect live contracts and obtain explicit reader authority first).
- Decision cache persistence and event-driven invalidation using existing database/storage owners; no new DB.
- Historical real-labelled evaluation datasets, calibration, threshold tuning, drift analysis, deterministic baseline comparison and measured false-positive/false-negative rates.
- Benchmark compatible local Score/Noul inference with real evidence; retain explicit unsupported state if not available.
- Genuine buyer-window sequencing, source-independence weighting, value-of-information economics, relationship graph historical change proofs.
- Audited shadow promotions into founder-facing CRM review queue, without automatic outbound.
- Multi-tenant productization, pricing and white-label packaging after internal commercial evidence.
- Full release gauntlet and production eligibility check before any live routing.

These are not implicitly activated by this code commit. No completed release or simulated green test constitutes commercial permission.

## 7. Source attribution / reuse policy

Research reference: Instantly, “Jev Just Changed Lead Generation Forever!” (2026-10-11); TypeSafe decision model documentation and the `bcharleson/jev-gtm-cookbook` MIT-licensed GTM cookbook. This implementation uses independently written EmpireOS-native contracts/patterns rather than vendoring external code or claiming external model performance. Any later imported MIT source files must retain the required license notice.
