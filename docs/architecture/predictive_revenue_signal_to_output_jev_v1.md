- recommendation_only=true;
- execution_authority=none.

Allowed output types:
- OPPORTUNITY_CREATE
- BUYER_MATCH_REVIEW
- BID_PROPOSAL
- PRICING_REVIEW
- OUTREACH_REVIEW
- CAMPAIGN_REVIEW
- RESEARCH_REQUIRED
- HOLD
- NO_ACTION

## Truth boundaries
- Signal strength is not probability unless calibrated evidence supports it.
- Bid amount is not expected value.
- Forecast expected value is not actual revenue.
- Conditional revenue is not guaranteed revenue.
- Recommendation is not authority.
- No outbound, allocation execution, terms acceptance, payment, settlement or
  revenue recognition is allowed in JEV.

## Placement
Canonical module target: `empire_os/predictive_revenue_jev.py`
Focused tests: `tests/test_predictive_revenue_jev.py`

The implementation must compose existing canonical modules and expose a single
Signal → Output packet suitable for Astra, Opportunity Factory, Buyer Matching,
Marketplace/Auction, Revenue Router and Founder surfaces.

## Verification
Required regression coverage:
- Predictive Revenue Formula
- Quant Brain
- Opportunity Evidence Normalizer
- Action Portfolio Optimization
- Revenue Exchange Optimization Bridge
- Opportunity Auction truth boundary

## Completion condition
JEV v1 is complete only when one deterministic, evidence-backed signal can be
compiled into a typed recommendation packet with explicit UNKNOWN fields,
evidence lineage, value economics, blockers and zero consequential authority.
