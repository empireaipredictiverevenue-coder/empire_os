# Founder Vertical Intelligence Runtime Read Surface V1

Date: 2026-10-02
Status: ARCHITECTURE CONTRACT
Change class: Read-only observability delta

## Purpose

Expose existing Permit, Property and Private Capital runtime projections through
the loopback-only Founder read API so product live-smoke tests can validate real
production evidence without direct database access or synthetic fixtures.

## Canonical owners

No product logic is moved.

- Permit runtime remains owned by permit_intelligence_runtime.
- Property runtime remains owned by vertical_intelligence_runtime.
- Private Capital runtime remains owned by vertical_intelligence_runtime.
- Founder service remains loopback-only and read-only.

## Endpoints

GET /v1/founder-vertical-intelligence/permit
GET /v1/founder-vertical-intelligence/property
GET /v1/founder-vertical-intelligence/private-capital

## Authority

Every response is observational only.

The router performs no:
- persistence;
- source acquisition;
- canonical DB writes;
- pricing mutation;
- checkout/payment action;
- outbound;
- live meeting action;
- revenue recognition.

It does not convert UNKNOWN evidence to zero/negative truth.

## Failure behavior

Missing runtime files/stores use the existing product runtime fail-closed
semantics. The API does not invent fallback data.

## Verification

- route contract tests;
- source runtime regressions;
- founder service route test;
- live loopback smoke after deployment;
- Private Capital remains UNKNOWN while its canonical evidence count is zero.
