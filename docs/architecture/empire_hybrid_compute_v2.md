# Empire Hybrid Compute V2

## State

OBSERVE ONLY.

No production execution authority.

## Purpose

Hybrid Compute V2 observes EmpireOS model-routing decisions and compares them
with the Empire Hybrid Compute policy without altering the selected route.

It composes existing canonical owners rather than replacing them.

## Canonical ownership

Model inventory and policy metadata:
`empire_os.model_registry.ModelRegistry`

Observed provider/model health:
`empire_os.model_health.ModelHealth`

LLM provider/model selection:
`empire_os.model_router.ModelRouter`

LLM execution:
`empire_os.llm_gateway.LLMGateway`

Observability:
`empire_os.telemetry`

Verified commercial learning:
`empire_os.economic_memory`

Predictive computation:
Predictive Cloud / Predictive Revenue canonical owners.

## V2 flow

WORKLOAD
→ HYBRID REQUEST
→ V1 HYBRID POLICY
→ MODEL REGISTRY OBSERVATION
→ MODEL HEALTH OBSERVATION
→ CURRENT MODEL ROUTER DECISION
→ SHADOW COMPARISON
→ TELEMETRY EVENT
→ EVIDENCE

V2 does not execute the recommended route.

## Invariants

- production_authority = false
- route_applied = false
- execution_performed = false
- no LLMGateway.chat()
- no LLMGateway.structured_chat()
- no ModelHealth.save()
- no database mutation
- no outbound action
- no payment authority
- no commercial acceptance authority
- no infrastructure mutation
- unknown remains unknown
- unavailable remains unavailable
- recommendation is not authority

## Route ownership

LOCAL_SMALL and LOCAL_STRONG are Hybrid Compute policy classes over canonical
local model candidates.

FRONTIER is a Hybrid Compute policy class over canonical remote model
candidates.

PREDICTIVE remains owned by Predictive Cloud / Predictive Revenue.

DETERMINISTIC remains owned by governed deterministic EmpireOS workflows.

HUMAN_GATE means no model execution should be promoted from this observation.

## Promotion gate

V2 cannot be promoted to live routing.

A later architecture contract must establish matched workload evidence for:

- quality
- latency
- reliability
- cost
- privacy
- failure behaviour
- route repeatability

Only then may a separate governed proposal request routing authority.

## Node Fabric V2.1 integration

Hybrid Compute is now composed with the canonical Node Fabric.

Canonical execution domains remain independently owned:

- Predictive workloads → Predictive Revenue / Predictive Cloud.
- Quantitative workloads → deterministic Quant Brain.
- Optimization workloads → Optimization Runtime and benchmark-gated solvers.
- Search intelligence → dedicated Search Intelligence runtime.
- Domain intelligence → canonical Founder Intelligence Node catalog.
- Model workloads → canonical Model Registry / Model Router.

Node discovery never grants execution authority.

A healthy node means its observed contract is available. It does not mean that
the node may perform outbound, payment, binding commercial, infrastructure, or
other founder-gated actions.
