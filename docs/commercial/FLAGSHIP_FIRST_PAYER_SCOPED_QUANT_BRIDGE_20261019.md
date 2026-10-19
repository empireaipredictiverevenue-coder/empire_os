# Empire AI — First-payer exact-source → Quant scoped bridge

19 October 2026 | Owner: feature/predictive-decision-control-20261018 | additive read-only review

## Purpose

Connect the **existing** Opportunity Factory / Business Development research request with the **existing** Quant Brain original input preflight, using the **same opaque first-payer opportunity reference**, current Radar market revision and same source key. This is a second-stage evidence integrity gate after the earlier v49/V43 shadow review, not an external send, CRM change, forecasting engine replacement or new agent.

## Implementation / contracts

- `empire_os/flagship_first_payer_scoped_quant_bridge.py` calls existing `review_current_first_payer_owner_handoff`, `review_source_epoch_reconciliation_runtime`, `review_one_commercial_evidence_request`, `market_identity_digest` and, **only when an existing authorized owner supplies a scoped source key and explicit model/Quant evidence**, `review_first_payer_quant_preflight`.
- The user-facing read-only operator accepts **no private opportunity key, tenant ID or first-party buyer evidence via terminal flags**, and never prints those inputs. `scripts/review_first_payer_scoped_quant_bridge_20261019.py --read-only`.
- Must see a `FOUR_STAGE_SOURCE_IDENTITIES_ALIGNED` and `CANONICAL_PATHWAY_REVIEW_READY` epoch before considering the selected source. Rechecks original `oppref_` digest from the supplied raw key, the current selected request fingerprint, exactly one matching Radar row, source `market_identity_digest` and niche. A stale or mismatched snapshot holds; no fuzzy match or other-market fallback.
- A public research row with tenant_id absent **does not prove tenant membership**, even if an opaque key matches. `tenant_scope_authenticated` is always false. Buyer name, contact, acceptance, compliant marketing route and prices cannot be derived from the Radar.
- If owner-supplied Quant numbers and scoped source receipts are included in a private in-process call, the existing Quant preflight reports **missing 11 original fields** or a **simulation-only, unauthenticated prospective candidate**. Its self-declared source labels are never an original model attestation or authenticated buyer receipt.
- No prototype itself invokes the original conversion registry writer. `original_forecast_registered=false` always. No outcomes are inferred; Economic Memory verified terminal-pair count remains unknown in this bridge.

## Canonical owners / what actually unlocks first revenue

1. **Existing Opportunity Factory** — maintain a coherent all-four source epoch, including intermittent Community Intent events.
2. **Existing CRM / Business Development buyer authority** — independently verify a specific real buyer organisation; approved niche/product/territory/postcode, suppression, written price/acceptance, current daily capacity and delivery route under the correct tenant and source key. An explicitly parsed price or matching record is *not* independently accepted contract terms.
3. **Existing Quant owner** — with source-available evidence *at forecast issue time*, independently validate probability model and version, time-to-revenue, revenue and cost intervals, uncertainty and accuracy evidence. Missing fields remain unknown; do not turn research rank into conversion probability.
4. **Original conversion registry DB owner** — separately approve any previously staged additive EmpireDB migration, dedicated authenticated tenant and writer/reader roles. Durable prospective issue and independent readback must precede the real outcome.
5. **Economic Memory owner** — join verified win/loss/settlement/fulfilment receipts, including denominator and failed/expired outcomes, before prequential calibration can be promoted. No training on self-labeled simulations or old v49 outcomes.

## Run

```bash
cd /home/ubuntu/empire_agents/predictive_decision_control_20261018
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m scripts.review_first_payer_scoped_quant_bridge_20261019 --read-only
PYTHONPATH=.:tests /srv/empire_os/.venv/bin/python -B -m pytest -q tests/test_flagship_first_payer_scoped_quant_bridge.py
```

The private in-process API `review_first_payer_scoped_quant_bridge(root,as_of=aware_datetime,tenant_id=...,opportunity_key=...,model_name=...,model_version=...,quant_inputs=...,source_receipts=...)` is intended **only for a separately authorized trusted existing-owner caller**, after it supplies source scoping. The function validates structure/identity, not the authenticity of the caller or its supplied terms.

## Production / commercial release

Feature branch only. No production deployment, active phone routing, emails, CRM/data mutations, original prediction recording, BSC funds movement, model training, or customer accuracy claim.

## Live owner-custody clarification (19 October, later review)

The exact opportunity `oppref_04c7a3720313eab3ec97` currently resolves to **Little Rock, Arkansas roofing market-research**, from `market_sweeps_revenue_gps`, rather than a verified tenant lead, signed buybox or the separate Chicago pilot. Its original Radar row has `tenant_id=None`, `org_id=None`, no confirmed buyer intent, and no verified commercial demand. The private buyer-projection inspection returned `CANONICAL_BUYER_GATEWAY_UNAVAILABLE`: **buyer count unknown**, not zero. The canonical four-stage identity join passed at review time; source snapshots can refresh independently.

The default read-only operator now resolves and checks the exact current source reference, current owner evidence fingerprint, market revision, upstream encoded market identity and downstream intake niche/category. It returns `UNOWNED_MARKET_RESEARCH_NOT_BUYER` and owner `business_development`, with next action `VERIFY_FIRST_PARTY_BUYER_INTEREST_TERMS_AND_TENANT_LINK`. This does not authenticate the tenant or establish a payer. The market-encoded source key and downstream niche must remain coherent even if four key sets are identical.

**Existing owner handoff:** Research one genuine organisation/person specifically buying the Little Rock roofing product, get a first-party reply or signed buying brief, exact product/location/postcode eligibility, source and consent/suppression, written price, demonstrable purchase/delivery capacity and commercially authorised offer. Preserve the original provider message/contract source, timestamps and source-key link through the authorised tenant-scoped CRM actor. Only then may the CRM owner provide an authenticated tenant-to-opportunity proof for private Quant review. Do not infer ownership from public market sweeps, assign an arbitrary org ID, or touch Lead Smart's Chicago pilot. After terms and source authentication, Quant still requires all 11 prospectively sourced numeric factors and separately enabled original prediction registry; Economic Memory needs actual independent outcomes before any accuracy claim.

No outbound, CRM mutation, DB read credential escalation, model promotion, forecasting or revenue recognition was performed by this branch. This is not evidence that Little Rock buyer demand or profitability is established.
