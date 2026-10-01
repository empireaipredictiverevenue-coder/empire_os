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

## V2 contract extension — 2026-10-01

### Correction

V1 established temporal validity but did not fully represent commercial
time-value erosion.

V2 separates three effects that must not be collapsed into one score:

1. commercial value retention;
2. buyer-specific need/capacity timing;
3. observed competitive saturation.

### Commercial value

Optional input: commercial_value.

A KNOWN retained value requires:
- retained_value_ratio in [0,1];
- explicit effective_from / effective_until timestamps;
- explicit basis: explicit_commercial_terms or validated_calibration;
- basis_ref;
- component-specific evidence refs;
- current evidence validity/freshness.

No interpolation, half-life, default discount rate or industry coefficient is
invented. Outside the evidenced effective interval the numeric value is UNKNOWN.

The candidate may later inform ERV recency_factor only after a separate reviewed
transport. It never mutates ERV directly.

### Buyer timing

Buyer need and buyer capacity are buyer/offer-specific windows.

A closed buyer need/capacity window:
- may make that buyer/offer route unavailable;
- must not expire Empire-owned inventory;
- must not erase other buyers or opportunities.

Need and capacity windows are assessed separately, then overlap is projected as
OPEN, FUTURE, NONE or UNKNOWN.

### Competitive saturation

Optional competitive_saturation input reports only an observed contested
fraction for an explicit market/offer/sample definition.

It is not:
- market share;
- probability_close;
- a pricing adjustment;
- a revenue factor.

No saturation penalty is inferred without a separately validated model.

### ERV ownership / double-count prevention

Existing ERV meanings stay distinct:
- recency_factor: reviewed retained commercial value only;
- time_discount_factor: financial present-value discount only;
- capacity_factor: separately evidenced capacity effect;
- probability_close: separate close-probability evidence.

V2 emits candidates and provenance only. It does not write any ERV field.

### Identity and malformed evidence

Opportunity identity must match the candidate being assessed.
Duplicate Radar identities cannot receive usable decay evidence.
Malformed component evidence becomes UNKNOWN for that candidate and must not
abort the whole Radar build.

### V1 compatibility change

Automatic ACTIVE -> recency_factor_candidate=1.0 is removed.
Generic hard expiry -> recency_factor_candidate=0.0 is removed.

Temporal validity is not the same thing as commercial value.

Top-level source_expires_at remains source-validity evidence.
Buyer need/capacity expiry moves to buyer-specific timing evidence and no longer
expires the owned opportunity.

### Required V2 verification

- explicit retained ratio preserved exactly;
- missing calibration remains UNKNOWN;
- current validity alone does not imply retained value=1;
- buyer closure is buyer-specific only;
- exact window boundaries and future windows;
- zero capacity is known FULL, missing capacity is UNKNOWN;
- competitive denominator/scope validation;
- zero contested sample observations are known zero only for the defined sample;
- identity mismatch and duplicate Radar identities fail closed;
- malformed one-candidate decay evidence does not abort Radar;
- existing Predictive Revenue arithmetic remains unchanged;
- no duplicate economic effect can be transported automatically;
- zero execution / accounting authority.

Status: V2 CONTRACT LOCKED / IMPLEMENTATION PENDING.
