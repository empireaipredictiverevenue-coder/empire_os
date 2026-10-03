# Empire Digital Avatar — Clone Fleet SaaS Quota / Billing Readiness V1

Date: 2026-10-02
Status: ARCHITECTURE CONTRACT
Change class: Architecture delta

## Purpose

Compose verified Clone Fleet meeting usage with Empire's existing SaaS
freshness/quota and usage-billing preview contracts.

This layer answers:
- is observed clone usage fresh and inside the tenant's verified entitlement?
- if verified commercial overage terms exist, what charge would be previewed?

It performs no subscription mutation, invoice creation, payment request, funds
movement, billing execution or revenue recognition.

## Inputs

Required:
- AvatarFleetMonthlyUsage from verified provider lifecycle events;
- observed_usage_limit from an external/canonical entitlement source;
- active_subscription boolean plus observation timestamp;
- tenant_isolation_verified boolean plus observation timestamp;
- usage observation timestamp from the verified monthly usage aggregate;
- timezone-aware now.

Optional billing preview additionally requires:
- verified commercial terms ref;
- verified overage pricing evidence ref;
- overage price in USDT micros per unit.

Caller-supplied values are evidence inputs, not authority. HTTP exposure remains
blocked until trusted tenant authentication / canonical entitlement retrieval
exists.

## Canonical reuse

Reuse exactly:
- saas_freshness.review_saas_quota_readiness
- saas_usage_billing.review_saas_usage_billing

Do not duplicate quota arithmetic or billing arithmetic.
Do not read legacy tenants.py SQLite plans/quotas/metering.

## Truth / authority

Verified usage is historical observed usage only.
Usage limit and subscription status must retain their own evidence freshness.

Quota review and billing review are previews.
They never prove payment, recognized revenue, active entitlement mutation or
future provider capacity.

All outputs retain execution_authority=none.

## Failure behavior

Tenant mismatch -> fail closed.
Usage period mismatch with requested billing period -> fail closed.
Stale/future usage/subscription/isolation evidence -> quota not ready.
Missing usage limit -> quota not ready.
Missing/invalid commercial terms or price evidence -> billing preview blocked.
Over-limit usage may be previewed as overage only when all other evidence is
fresh and verified.

Zero verified usage is not fabricated by this layer; upstream meter must supply
a verified monthly aggregate.

## Verification

Required:
- fresh in-limit usage -> quota ready/available;
- exact limit -> exhausted;
- over limit -> over_limit;
- stale usage/subscription/isolation blocks readiness;
- inactive subscription blocks;
- unverified isolation blocks;
- tenant mismatch blocks;
- verified overage terms produce preview only;
- missing terms/price evidence blocks preview;
- no invoice/payment/funds/revenue authority;
- full Avatar/Fleet regression remains green.
