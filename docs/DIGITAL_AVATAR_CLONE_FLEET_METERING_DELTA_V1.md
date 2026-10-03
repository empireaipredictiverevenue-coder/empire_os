# Empire Digital Avatar — Verified Clone Usage Metering V1

Date: 2026-10-02
Status: ARCHITECTURE CONTRACT
Change class: Architecture delta

## Purpose

Produce evidence-backed tenant usage observations for Digital Avatar Clone Fleet
without treating plans, assignments or provider attempts as billable activity.

V1 meters one unit for a provider-verified successfully completed meeting
session. It does not charge, invoice, request payment or recognize revenue.

## Canonical placement

Sources:
- validated AvatarFleetRuntimeBinding for tenant/avatar scope;
- Recall verified lifecycle runtime state.

Reuse:
- empire_os.saas_scale.UsageObservation;
- SaaS freshness/quota review;
- commercial usage/billing review downstream when terms are verified.

Forbidden source:
- legacy tenants.py SQLite metering/quota tables.

No Migration 018 change.

## Verified completed-meeting rule

A usage event is eligible only when all are true:
- runtime tenant/avatar binding is valid and zero-authority;
- lifecycle meeting_id and bot_id are present;
- lifecycle avatar_id equals runtime avatar_id;
- truth_class == VERIFIED;
- status_code == done;
- joined_meeting == true;
- terminal == true;
- fatal == false;
- at least one lifecycle verification/evidence ref exists;
- lifecycle execution_authority == none;
- lifecycle speech_execution == false;
- updated_at is timezone-aware.

Planned, assigned, dispatch-ready, waiting-room, joining, active-but-not-terminal,
fatal and media-expired states do not produce completed-meeting usage.

## Identity / idempotency

Usage identity is deterministic from:
tenant_id + avatar_id + meeting_id + metric.

Provider retries or repeated materialization of the same completed meeting
produce the same usage_key and must dedupe to one unit.

The monthly period is derived from verified lifecycle updated_at in UTC.

## Output

AvatarFleetVerifiedMeetingUsage:
- tenant_id;
- avatar_id;
- meeting_id;
- bot_id;
- usage_key;
- metric=digital_avatar_verified_meeting_session;
- units=1;
- period=YYYY-MM;
- observed_at;
- evidence_refs;
- billable_candidate=true;
- commercial_terms_bound=false;
- charge/payment/revenue execution=false;
- execution_authority=none.

Monthly aggregation may convert verified events into Saas UsageObservation for
quota/readiness review. It still does not make the units billable: pricing and
verified commercial terms remain separate downstream gates.

## Failure / isolation

Cross-tenant events in one aggregate fail closed.
Same usage_key with conflicting data fails closed.
Missing/invalid lifecycle evidence produces no usage event.
Zero verified events do not fabricate a positive observation.
No SQLite fallback is allowed.

## Verification

Required:
- verified done+joined lifecycle creates exactly one unit;
- waiting/active/fatal/media-expired do not meter;
- avatar mismatch rejected;
- non-VERIFIED lifecycle rejected;
- missing evidence rejected;
- duplicate same meeting dedupes;
- conflicting duplicate fails closed;
- monthly period derives from UTC timestamp;
- cross-tenant aggregation fails closed;
- conversion to SaaS UsageObservation has zero execution authority;
- no invoice/payment/revenue side effects;
- full Avatar/Fleet regression remains green.
