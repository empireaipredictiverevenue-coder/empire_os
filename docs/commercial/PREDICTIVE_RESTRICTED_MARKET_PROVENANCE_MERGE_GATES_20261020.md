# Predictive Revenue — Restricted Source Provenance and Merge Safety

**20 October 2026 | Predictive Decision Control isolated feature branch | no production changes**

## Why this matters to the flagship Predictive system

Empire AI must learn from **actual first-party purchases and realised customer value**, rather than treating a company's presence, a prospect, a positive message classification, a search result or a graph relationship as a sale. Profitability, causal scenario decisions, portfolio playbooks and calibrated models become dangerous if source lineage is wrong.

The existing Market GPS materialiser in production is a **restricted read-only source**, not an authoritative source for authenticated direct buyers, payments or automatic market activation.

### Critical source contract discovery

Production file `/srv/empire_os/empire_os/market_sweep_revenue_gps.py` is **not identical** to the older producer in the isolated Predictive branch.

| Concern | Existing production GPS | Older feature-branch GPS producer |
| --- | --- | --- |
| Market source | Restricted SQL `RESTRICTED_MARKET_QUERY` under `empire_intelligence_materializer` | RPC `public.get_market_sweep_revenue_gps` |
| Canonical RPC availability | **No** `get_market_sweep_revenue_gps` RPC exists | Assumes RPC exists |
| Database intent | `SET TRANSACTION READ ONLY` and bounded row projection | Different original interface |
| Reply-lineage provenance | Separate `REPLY_LINEAGE_QUERY`, restricted source scope, explicit unauthenticated flags | No equivalent projection |
| Buying authority | None; all replies/counts unverified | Must **not** inherit buying permission |

**Do not replace, merge over or deploy the older producer.** The source owner must reconcile current production implementation into the merge base and review the exact differences. The Predictive owner has not edited either original producer. New tests against the old producer remain synthetic, and the live runtime adapter must remain strict rather than default missing provenance fields to zero.

## Newly implemented interfaces

### 1. `empire_os/predictive_market_restricted_provenance.py`

`review_restricted_reply_lineage(source,territory,as_of=...)`

- Requires the already-validated original Revenue GPS territory evidence cards and **recomputes those cards from the exact original source**; checks source epoch, original revision SHA256 and original card contents to block a fake or drifted territory handoff.
- Requires the original `empire.market_gps_restricted_reply_lineage.v1` observation and its original `90 day` window. The territory source has a separately bounded `1–31 day` window. These **do not represent the same cohort**, even when generated in the same run.
- Verifies an internally consistent count partition: observed reply records, intent-pointer presence, matched outbound intents, matched prospects, unmatched and missing links, and unverified positive classifications.
- Requires *false* for original provider message authentication, contact identity, provider thread, tenant and buyer-intent authentication and inferred commercial demand. A positive reply classification or matching outbound-intent pointer is **not authenticated buyer demand**.
- Requires zero unverified replies/classifications in the narrow current market snapshot; broader original 90-day reply-lineage observations may be nonzero but cannot be attributed to a specific market, prospect or customer.
- Returns aggregate, anonymous diagnostic counts and seven precise first-party authentication/economic next steps. Returns `independent_committed_buyer_count=null`, `paid_order_count=null`, `calibration_training_allowed=false`, `outbound_allowed=false`.
- Any source claim about buying status, unexpected timestamp, inconsistent counts, mismatched source revision or raw private data access is held rather than promoted.

`review_restricted_reply_lineage_runtime(repo_root,as_of=...)`

Reads only `runtime/market_sweeps/revenue_gps_latest.json`, reusing the strict read-only territory adapter. No new DB query, raw reply text, private contact file, message body, licence bypass, crawler or external API call.

### 2. Static original-producer compatibility review

`review_market_gps_merge_compatibility(feature_root,production_root)`

Reads only the existing **source-code implementation file** from the two explicitly specified roots and checks use of restricted SQL, read-only transactions, reply-lineage projection and absence of the obsolete RPC dependency. This is a **static source-review indicator**, not a verified security audit or permission to merge.

Observed:
- Production source supports the required restricted query, read-only transaction, and lineage projection.
- Feature-branch older source still depends on the unavailable RPC.
- SHA256 source content revisions differ.
- Status `SOURCE_OWNER_MERGE_REVIEW_REQUIRED`.
- Blockers `FEATURE_MARKET_PRODUCER_MUST_NOT_REPLACE_RESTRICTED_PRODUCTION_SOURCE` and `SOURCE_OWNER_RECONCILE_PRODUCER_CODE_REVISION_BEFORE_MERGE`.
- `merge_source_producer_authorized=false` always.

### 3. Operator

`scripts/review_predictive_market_source_ownership_20261020.py`

```bash
cd /home/ubuntu/empire_agents/predictive_decision_control_20261018

PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_predictive_market_source_ownership_20261020 \
  --read-only
```

The live check at the examined 20 October 2026 checkpoint reported:

- `RESTRICTED_REPLY_PROVENANCE_RESEARCH_ONLY`;
- **0 source-observed reply-lineage rows** in the existing separate 90-day restricted snapshot;
- both original-market and original-forecast/customer-buying authentication still unavailable;
- source producer compatibility `SOURCE_OWNER_MERGE_REVIEW_REQUIRED` with two distinct blocker reasons.

This is **not** an enterprise-wide claim that no messages, buyers, payments or contracts exist in any other source.

### Tests

`tests/test_predictive_market_restricted_provenance.py` validates source identity, timestamp spoofing, counts arithmetic, changing producer contract, forgery of buyer intent, invalid authority, misattributed territory revision, source-code drift, read-only original snapshot inputs and untrusted private fields. The prior `tests/test_predictive_market_evidence_binding.py` remains intact.

## Next engineering owner handoffs

1. **Market GPS owner / Source Intelligence:** reconcile the restricted production source with the feature-branch merge base. Preserve explicit SQL read-only, restricted column access, 90-day reply-lineage diagnostics and source owner policy. Do not reintroduce the missing RPC.
2. **Buyer/CRM original provider evidence owner:** authenticate original inbound message ID, provider thread binding, genuine person/company contact, tenant and buying authority, accepted commercial terms, territory, price and capacity. The existing deterministic verifier/CRM owns writes.
3. **Economic Digital Twin/Spatial owner:** bind canonical geographic IDs and exact source-revision ancestry, not city-text aliases, to licensed source snapshots for competitor pricing, costs, seasonality, weather and local operational capacity.
4. **Finance/Commerce/Customer Success:** independently authenticate original purchase, delivery/fulfilment, settlement, refund, cohort costs, customer time/money value and recognised gross profit. Unverified estimates never become accounting.
5. **Original Scientific Quant registry:** prospectively register and read back an actual original forecast under the appropriate existing DB role **before** outcome observation. This feature does not register it, issue an automatic model probability or calibrate GP.
6. **Decision Control / Owner review:** take verified evidence and original forecast registry proof into the existing governed playbook and portfolio system; maintain founder-approved capital/contact policy.

**Source-version compatibility must be resolved by its owner before merge. No production files, service/timer, website, model, database or external campaigns were modified in this feature.**

The original north-star remains:

**Predicted Gross Profit → Realized Gross Profit → Prediction Error → Better Allocation.**
