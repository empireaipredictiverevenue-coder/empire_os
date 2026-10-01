# Opportunity Revenue Evidence Bridge

Date: 2026-10-01
Status: verified

## Purpose

Transport only explicit, fresh, opportunity-bound canonical observations into
Predictive Revenue factor inputs. This bridge never estimates missing factors.

## Owner

- empire_os/opportunity_revenue_evidence.py
- tests/test_opportunity_revenue_evidence.py

## Positive example

One fresh canonical observation binds demand=0.5 to one opportunity with an
evidence reference. Radar may expose demand=0.5 while every other missing
Predictive Revenue input remains UNKNOWN.

## Negative examples

- priority score is not demand;
- buyer capacity is not buyer_match;
- product price is not LTV;
- stale, future, naive-time or ambiguous observations are rejected;
- duplicate factor observations are rejected;
- missing factors are never filled with zero.

## Authority

OBSERVE only. No outbound, allocation, pricing, terms, payment, fulfilment,
revenue recognition, migration or production-deploy authority.

## Verification

2026-10-01: bridge + Opportunity Radar + Predictive Revenue suites: 106 passed.
