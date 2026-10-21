# Predictive Comparison — Original Price Provenance & Evidence Action Queue
2026-10-21. This is a private OBSERVE-only improvement to the existing Predictive Comparison release, not new price approval.

## Direct observation
The root-owned catalogue currently has 86 distinct product codes:
- **35** founder-approved *price-source records* (includes the five previously approved flagship enterprise prices); this alone proves neither actual paying customers nor independently accepted terms.
- **26** recovered MRR SKUs with agreed **legacy consensus** nominal amounts requiring founder economics review; no automatic approval.
- **20** recovered MRR SKUs with one historical **candidate** price from the prior pricing/metadata source, no approved amount; the candidate is never promoted to the price output.
- **5** recovered MRR SKUs with **conflicting historical candidate prices** and no approved amount: `meetily_enterprise`, `meetily_pro`, `scraper_enterprise`, `scraper_pro`, `scraper_starter`.

Existing cost policy ceiling review: 26 founder-priced SKUs have valid scenario policies, meeting their internal minimum under those cap assumptions. The remaining **nine** founder-approved price-source SKUs lack complete comparable policy ceilings. Actual labour, compute, merchant charges, data rights, taxes, refunds, contract acceptance and realised profit remain unverified. None of these new counts authorises repricing, public claims, outbound, payments, registry changes or model training.

## Previous comparison defect
The existing `catalogue_price_source_approval_state` field looked only for `commercial_approval_state`, which is absent for founder-approved source records. This made **35 source-approved prices display UNKNOWN** alongside legacy prices requiring review. Correction: validate four source custody classes from the original price basis, including its source type, record status, consensus/single-source/conflict policy and original candidate fields. Preserve the actual original price and currency without resolving conflicts or converting currencies.

## Private execution surfaces
- `empire-predictive-comparison`: safe 86-product aggregate and new provenance counts.
- `empire-predictive-comparison --gaps`: bounded action queues based on original root-owned catalogue; 5 founder price resolution, 20 unpriced economics, 26 legacy-priced economics, 9 source-approved prices with missing cost caps and 25 products without adjacent vendor research matches. These queues overlap; do not sum them as unique products.
- `empire-predictive-comparison --product meetily_pro`: only the selected original SKU and its price/evidence/adjacent research record, avoiding the 225-KB `--all` output. Unknown SKU, unusual token or unsafe flag held without customer detail.
- `empire-predictive-comparison --all`: original full research view still available.

## ASTRA GPT-6 review
An ASTRA independent review is still **NOT_EXECUTED**. Challenge the pinned source commit, original root-owned snapshot hash, disputed original price candidates, exact source timestamp and founder authority, vendor product-and-contract unit, data rights, internal costs vs actual ledger, gross margin claims, customer value, right-censored forecast outcomes, original conversion registry and tenant isolation. No fake audit approval or automatic commercial pricing changes.

## Guarded release
The existing feature-branch immutable release builder pins the gap module, adds `comparison-gaps` and `comparison-product SKU` commands with static read-only flags, and shadow-tests both against the same root-owned source as the original comparison. Production Cloud materializer, Founder API, EmpireDB roles, customers and financial gates remain unchanged. Promote only the user's reversible private comparison alias after signed-source hash inventory and aggregate/product tests pass.
