# Hermes OBSERVE Execution Contract Delta

Date: 2026-10-01
Status: implementation in progress

## Diagram

ExecutionRequest (OBSERVE)
-> Execution Plane Dispatcher
-> Hermes control job
-> isolated Hermes worktree
-> read / inspect / reason only
-> result evidence

No repository mutation, canonical-data mutation, outbound, payments, settlement,
revenue recognition, production deploy or authority expansion.

## Root cause

The dispatcher serializes `allowed_paths=[]` and `lease_resources=[]` for a
valid OBSERVE-only Hermes request.

`HermesJob.from_mapping()` currently rejects an explicitly supplied empty
`allowed_paths` list, so a valid zero-scope OBSERVE request cannot enter the
Hermes queue.

Simply omitting the fields is unsafe because the legacy default is
`SAFE_EDIT_PREFIXES`, which would give an OBSERVE job a broad edit scope.

## Contract delta

For `authority=observe`:
- explicit empty `allowed_paths` is valid and means zero editable paths;
- explicit empty `lease_resources` is valid and means zero mutation leases;
- the Hermes worker skips mutation-lease acquisition entirely for OBSERVE;
- any changed path fails changed-path validation;
- no production or consequential authority is added.

For `authority=internal_write`:
- empty `allowed_paths` remains invalid;
- empty `lease_resources` remains invalid;
- existing bounded path and lease rules remain unchanged.

## Positive example

An architecture-audit job is dispatched to Hermes with OBSERVE authority and
empty edit/lease scopes. Hermes may inspect source and return findings, but any
attempted file mutation fails verification.

## Negative example

An INTERNAL_WRITE backend task with an empty edit scope remains rejected. The
OBSERVE exception must never widen mutation authority.

## Verification

Required:
- Hermes schema tests for zero-scope OBSERVE and fail-closed INTERNAL_WRITE;
- dispatcher regression proving OBSERVE Hermes payload is accepted;
- adjacent execution-plane and Hermes-control tests;
- live queue of one OBSERVE-only Hermes audit;
- no production deploy or canonical-data mutation.
