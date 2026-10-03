# Empire Hybrid Compute V4

## Purpose

Turn verified Hybrid Compute benchmark evidence into governed routing
recommendations.

## Authority boundary

V4 is shadow-only.

It may recommend a candidate.

It may not:

- change ModelRouter production routing
- execute a recommendation
- promote a model
- grant commercial authority
- bypass founder-gated actions
- convert benchmark evidence into revenue truth

## Current measured local evidence

The local ladder contains matched quality, reliability and latency evidence.

Resource economics remain incomplete.

Model size is therefore not used as a proxy for economic value.

## Provider health

Benchmark execution failures can be interpreted as observations but are not a
replacement for canonical ModelHealth.

Hard execution failures such as permission/authentication restrictions should
be excluded by the future production integration until fresh evidence changes
their state.

Transient service failures are degraded evidence, not permanent exclusions.

## Future activation

Production integration must consume canonical ModelHealth and this policy's
quality/latency evidence, then pass through the existing Empire authority
boundary.

Readiness is not authority.

## Canonical Node Fabric health integration

V4 recommendations now intersect matched benchmark evidence with canonical
Node Fabric health before recommending a local model.

Registered local model identities:

- qwen2.5-coder:1.5b — LOCAL_SMALL
- qwen2.5-coder:7b — LOCAL_STRONG
- qwen2.5-coder:14b — LOCAL_STRONG
- qwen3-coder:30b — LOCAL_STRONG

A benchmarked model that is not represented by a healthy canonical runtime node
is excluded from the current shadow recommendation.

This remains recommendation-only. Node health does not grant execution,
commercial, outbound, payment or infrastructure authority.

All founder-gated actions terminate at HUMAN_GATE.
