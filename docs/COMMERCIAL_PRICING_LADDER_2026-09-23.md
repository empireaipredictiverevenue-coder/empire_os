# Empire Launch Pricing Ladder — Founder Approval Proposal

Date: 2026-09-23
Status: PROPOSED — NOT BINDING UNTIL FOUNDER APPROVES EXACT LADDER

Founder approval reference: `founder_approval:2026-09-23:commercial_pricing_ladder_v1`.

The 12 previously unpriced active catalog products are now VERIFIED in the canonical catalog. The already-verified Empire Opportunity Intelligence Pilot remains
unchanged at $1,500 flat.

## Positioning evidence

Current public pricing used only as positioning benchmarks:
- Ahrefs Lite is about $129/month and Standard about $249/month.
- Semrush SEO starts around $139/month, with higher tiers around $250-$500.
- Local Falcon starts around $25/month and scales to about $200/month.
- SerpApi starts around $25/month, with production tiers around $150/month.

Empire prices below are company policy proposals. They are not claims that
Empire has historically sold these products at these prices. Cost numbers are
launch policy ceilings, not observed actual costs.

## Proposed launch ladder

| Product | Commercial model | Price |
|---|---|---:|
| Local Search & Maps Grid Intelligence | monthly | $79/mo |
| Content Decay & Cannibalisation Monitor | monthly | $99/mo |
| AEO / GEO AI Visibility | monthly | $149/mo |
| Authority & Backlink Intelligence | monthly | $149/mo |
| Competitor Search Gap | one-off report | $199 |
| Search Opportunity Map | one-off report | $249 |
| Technical Search Audit | one-off audit | $299 |
| Search Growth Command | monthly | $299/mo |
| SERP Intelligence API | monthly base | $99/mo |
| Permit Intelligence | monthly | $499/mo |
| Property Intelligence | monthly | $799/mo |
| Private Capital & Roll-Up Intelligence | monthly | $1,500/mo |

SERP Intelligence API launch allowance:
- 10,000 requests/month included;
- proposed launch overage: $0.01/request.

## Launch policy cost ceilings

These are governance ceilings only, not observed actual costs.

| Product | Acquisition ceiling | Fulfilment ceiling | Minimum GM |
|---|---:|---:|---:|
| Local Search Grid | $8 | $12 | 65% |
| Content Protection | $10 | $15 | 65% |
| GEO AI Visibility | $15 | $20 | 65% |
| Authority Intelligence | $15 | $20 | 65% |
| Competitor Search Gap | $20 | $30 | 65% |
| Search Opportunity Map | $25 | $50 | 65% |
| Technical Search Audit | $30 | $60 | 65% |
| Search Growth Command | $40 | $60 | 65% |
| SERP Intelligence API | $15 | $20 | 60% |
| Permit Intelligence | $75 | $75 | 65% |
| Property Intelligence | $120 | $120 | 65% |
| Private Capital Roll-Up | $200 | $250 | 65% |

The governed catalog validator will reject any product version whose policy
ceilings fail its minimum margin requirement.

## Existing verified offer

The existing managed_service / Empire Opportunity Intelligence Pilot remains:
- $1,500 flat pilot;
- $300 acquisition ceiling;
- $300 fulfilment ceiling;
- 55% minimum margin policy.

No repricing is proposed for that product.

## Founder gate

Approval of this exact ladder authorizes these amounts to be used as
founder-policy evidence for pending catalog versions and independent
verification.

Approval does not send outbound, accept buyer terms, request or move funds,
create fulfilment, recognize revenue, or expand Astra authority.


## Production verification

On 2026-09-23 the exact 12-product ladder was:
- staged as governed PENDING catalog versions;
- validated against the approved prices, units, cost ceilings and margin floors;
- verified through `public.decide_commercial_product_version(...)`;
- confirmed with zero remaining PENDING versions.

The dedicated verifier login could not be impersonated through the Supabase MCP
maintenance connection because that connection cannot `SET ROLE`. Verification
therefore ran through the privileged Postgres maintenance channel using the
same governed verifier function and was recorded as
`maintenance_verification_after_founder_approval`.

Every verified version reports `actual_revenue=false`; catalog verification
does not recognize revenue.
