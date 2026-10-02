# Decision-Maker Personhood Hardening V1

## Goal

Prevent page labels, marketing phrases, form placeholders and organization
fragments from being promoted as named buyer decision-makers.

## Flow

First-party site probe
  -> semantic personhood validation
  -> role-authority validation
  -> Buyer Acquisition Scout defensive filter
  -> ICP/account intelligence
  -> deferred enrichment / review readiness
  -> governed outbound gate

## Truth rules

A candidate person must:
- look like a human name, not merely title-case text;
- avoid known non-person vocabulary such as press/release, strategy/systems,
  agency, association, form-name labels, platform/network terms;
- have a title that maps to at least an influencer-level commercial role before
  Buyer Acquisition Scout may retain it as first-party people evidence;
- retain first-party evidence URL/provenance where supplied.

Structured-data Person records are subject to the same personhood filter as
visible-text extraction. Schema markup is evidence, not automatic truth.

The scout repeats the filter defensively before ICP/account scoring and
persistence, so a malformed upstream extractor cannot promote a false person.

## Authority

This change is evidence filtering only. It does not create prospects or buyers,
authorize outreach, accept terms, allocate capacity, request payment, recognize
revenue, or expand database authority.
