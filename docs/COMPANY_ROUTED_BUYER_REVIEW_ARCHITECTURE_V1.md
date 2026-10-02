# Company-Routed Buyer Review Architecture V1

## Goal

Surface a small secondary revenue lane when Empire has:
- a named economic buyer backed by first-party company-domain evidence; and
- a verified company email route on that same company domain; but
- no verified person-bound email.

This lane is review-only. A company inbox must never be represented as the
person's own email and must never inherit standing auto-send authority.

## Canonical flow

deferred buyer
-> named economic buyer evidence
-> same-company-domain verification
-> verified first-party company email route
-> ambiguity check
-> founder review queue
-> explicit founder gate before any future company-routed send

## Fail-closed rules

- person name must pass Empire personhood validation;
- decision role must be economic buyer with score >= 0.70;
- person evidence URL domain must match the company email domain;
- company route must be verified and first-party observed;
- route remains person_bound=false;
- tied top-authority people are marked ambiguous;
- no outbound intent, database write, commercial terms, payment or revenue action;
- no inference that the inbox belongs to the named buyer.

## Authority

OBSERVE / review preparation only.
