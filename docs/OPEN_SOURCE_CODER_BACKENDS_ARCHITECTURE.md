# EmpireOS Open-Source Coder Backends — Architecture Contract

Status: OBSERVE / governed builder foundation
Authority expansion: none

## Purpose

EmpireOS already owns the coding-team control plane: routing, mutation leases,
allowed paths, disposable workspaces, verification, proposal branches,
Promptfoo gates and production promotion policy.

Open-source coding engines are subordinate implementation backends. They may
improve edit quality, repository context and tool execution, but they do not
become the authority layer.

## Canonical builder flow

Founder / Astra / AGI
-> Agent & Tool Execution Plane
-> capability ledger
-> governed worker
-> disposable workspace
-> mutation backend
-> changed-path enforcement
-> focused tests
-> proposal branch
-> independent verification
-> Promptfoo / policy gate
-> human or governed promotion

## Mutation backends

### Empire Structured Patch

Existing native backend. Produces one machine-checkable patch proposal and
validates it before applying.

Capability: empire_coder.structured_patch_mutation

### Aider

Aider is integrated as an optional secondary mutation engine inside the Empire
Coder sandbox. It is not a standalone authority-bearing worker.

Required properties:
- isolated installation from the EmpireOS Python environment;
- one-shot scripted invocation;
- disposable clone only;
- explicit editable-file allowlist;
- no auto commits;
- no shell-command suggestions;
- no automatic external URL detection;
- no repository .env/config loading;
- analytics disabled;
- EmpireOS performs its own changed-path validation;
- EmpireOS performs its own pytest verification;
- proposal branch only;
- no production deployment.

Capability: empire_coder.aider_mutation

Aider may be selected only after a live disposable-clone capability probe
passes. installed != mutation-capable.

### OpenHands Software Agent SDK

OpenHands is a workspace/tooling architecture backend, not an EmpireOS control
plane replacement.

Useful capabilities to reuse:
- typed tool/action contracts;
- workspace abstraction;
- ephemeral agent workspaces;
- conversation/state persistence;
- skills;
- MCP integration;
- security validation;
- multi-agent task decomposition.

Initial EmpireOS integration is adapter/readiness only. OpenHands mutation must
earn a separate capability before receiving write jobs.

Capability: empire_coder.openhands_workspace

## Failover

For an Empire Coder mutation job:

1. use the configured/preferred proven backend;
2. if the native structured-patch backend fails transiently and Aider mutation
   is proven, attempt Aider in the same disposable clone;
3. if no proven backend remains, fail closed.

A backend failure never means success.

## Model routing

The mutation backend and model router are separate.

Aider should normally use the loopback OmniRoute OpenAI-compatible endpoint,
allowing EmpireOS model policy/failover to remain centralized.

A tiny local model may remain useful for bounded planning/classification, but it
must not be promoted to mutation work merely because it responds to prompts.

## Promotion

No open-source coder backend is production-ready because it is installed.

Promotion requires:
- health check;
- disposable-clone mutation probe;
- exact changed-path enforcement;
- focused test pass;
- no production working-tree mutation;
- no unexpected commits;
- benchmark against the current backend;
- independent verification;
- capability ledger evidence.

## Truth and authority

These integrations grant no:
- production deploy authority;
- database mutation authority;
- outbound authority;
- payment/fund authority;
- commercial terms authority;
- revenue recognition authority;
- permission expansion.

They improve code-generation machinery only.
