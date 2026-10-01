# Commercial Opportunity Decay Architecture Delta

Date: 2026-10-01
Status: IMPLEMENTATION IN PROGRESS

## Diagram

Canonical opportunity evidence
-> Commercial Opportunity Decay assessment
-> Opportunity Radar / Revenue Router context
-> reviewed recency evidence
-> existing Predictive Revenue ERV inputs

The canonical Predictive Revenue formula is unchanged.

## Owner

New canonical assessment owner:
- `empire_os/commercial_opportunity_decay.py`

This is separate from:
- SEO/content decay;
- generic opportunity scoring;
- revenue recognition;
- buyer intent;
- execution.

## Evidence contract

Supported temporal evidence:
- opportunity observation timestamp;
- explicit revalidation timestamp;
- explicit source expiry;
- explicit buyer-need window;
- explicit buyer-capacity window;
- explicit source freshness policy window.

Every non-UNKNOWN assessment requires evidence references.

## States

- `ACTIVE`: explicit validity/freshness evidence is still current.
- `STALE`: an explicit freshness policy has elapsed without revalidation.
- `EXPIRED`: an explicit hard commercial/source window has passed.
- `UNKNOWN`: insufficient or invalid temporal evidence.

Precedence:
`EXPIRED > STALE > ACTIVE > UNKNOWN`.

## Formula boundary

This module never mutates Predictive Revenue inputs.

It may expose a **candidate** recency factor:
- explicit hard expiry -> candidate 0.0;
- explicitly current validity/freshness -> candidate 1.0;
- stale or insufficient evidence -> candidate UNKNOWN / None.

The candidate is recommendation-only and must be reviewed/transported through a
separate evidence contract before entering ERV.

No continuous numerical decay curve is invented without calibrated evidence.

## Positive example

An opportunity observed 30 days ago but explicitly revalidated today with a
buyer-need window still open is ACTIVE. Age alone does not penalize it.

## Negative examples

### Hard expiry
A permit opportunity has an explicit buyer-need deadline that has passed.
Assessment is EXPIRED and candidate recency is known zero.

### Stale evidence
A source has a documented 24-hour freshness policy and has not been revalidated
for 48 hours. Assessment is STALE. Do not invent a numeric 0.5 factor.

### Missing evidence
A record has only an old created_at timestamp and no freshness/expiry contract.
Assessment is UNKNOWN, not stale.

## Verification

- explicit expiry precedence;
- recent revalidation overrides age-only concern;
- freshness-window stale detection;
- missing evidence remains UNKNOWN;
- timezone-naive timestamps rejected;
- candidate factor never becomes revenue or execution authority;
- locked Predictive Revenue formula tests remain unchanged and green.

## Authority

OBSERVE only. No allocation, outreach, terms, payment, settlement, fulfilment,
revenue recognition, database migration or production deploy authority.
