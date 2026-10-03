# Empire Digital Avatar — Tenant-Namespaced Recall Activation Materialization V1

Date: 2026-10-02
Status: ARCHITECTURE CONTRACT
Change class: Multi-tenant persistence architecture delta

## Purpose

Materialize an already approved, fleet-scoped Recall SHADOW activation into
tenant-isolated local runtime directories while reusing the canonical activation
store and session writer.

This layer performs local persistence only. It never calls Recall and never
executes a meeting join.

## Problem solved

The canonical Recall activation store uses meeting_id filenames. In a
multi-tenant Clone Fleet, two tenants may legitimately have the same external
meeting identifier or local canonical meeting key.

A shared root would therefore permit filename collisions.

## Namespace

V1 derives a deterministic filesystem scope:
tenant_scope_key = "tenant-" + first 24 hex chars of SHA-256(tenant_id).

The raw tenant_id is not used as a path component.

Within that scope:
- sessions live under <session_base>/<tenant_scope_key>/
- activation records live under <activation_base>/<tenant_scope_key>/

Canonical files inside the tenant root keep their existing meeting_id-based
format.

## Inputs

Required:
- AvatarFleetRecallActivationPreparation;
- session_base_root;
- activation_base_root.

The activation preparation must still be pre-execution:
- activation_ready=true;
- fleet_scope_verified=true;
- activation_persisted=false;
- provider_call_performed=false;
- meeting_join_performed=false;
- no speech/chat/commercial/payment/revenue execution.

## Canonical reuse

Call materialize_recall_shadow_activation() exactly once against the derived
tenant-scoped roots.

Do not duplicate its fingerprint, atomic-write, conflict or session persistence
logic.

## Output

AvatarFleetRecallMaterialization:
- tenant_id;
- tenant_scope_key;
- meeting_id;
- avatar_id;
- session_root;
- activation_root;
- activation_record;
- activation_plan_sha256;
- materialization_ready=true;
- activation_persisted=true;
- session_persisted=true;
- provider_call_performed=false;
- meeting_join_performed=false;
- speech/chat/commercial/payment/revenue execution=false;
- execution_authority=none.

## Isolation / idempotency

Same tenant + same activation packet -> idempotent canonical materialization.

Same tenant + same meeting_id + different activation fingerprint -> fail closed
through canonical activation-store conflict handling.

Different tenants + same meeting_id -> separate tenant-scope roots and no
collision.

No fallback to global/unscoped roots is permitted.

## Security

No API key is accepted.
No provider transport is accepted.
No raw media is persisted.
No public HTTP endpoint is added.

This layer must not import or call recall_shadow_execution.

## Verification

Required:
- exact same tenant packet materializes idempotently;
- two tenants with same meeting_id produce distinct scope roots;
- conflicting same-tenant activation fails closed;
- scope key contains no raw tenant path separators;
- canonical session + activation files are created inside tenant root;
- no provider call/join state is written;
- full Fleet/Avatar/Recall regression remains green.
