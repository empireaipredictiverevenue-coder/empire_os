# Empire AI — Intelligence Router Architecture

Date: 2026-09-22
Status: CANONICAL INTELLIGENCE-PROVIDER ARCHITECTURE

## Principle

EmpireOS must be **intelligence-upgradable without being authority-upgradable by default**.

Astra, departments and agents request capabilities. They do not hard-code a
specific model vendor.

Canonical flow:

**Astra / Department**
→ Intelligence Requirement
→ Intelligence Router
→ Deterministic Quant OR Model Router
→ selected execution engine
→ Verifier / Control Fabric
→ governed result

## Intelligence classes

### deterministic_quant
For:
- economics
- probability/calibration review
- Monte Carlo
- risk
- portfolio analysis
- value of information
- quantitative verification

Engine:
- Quant Brain

### local_fast
For:
- classification
- extraction
- summarization
- lightweight transformations

### local_reasoning
For:
- private/local reasoning
- coding/research tasks suited to local hardware
- tasks where local execution economics/privacy justify it

### frontier_fast
For:
- high-quality general inference where reasoning mode is unnecessary

### frontier_reasoning
For:
- difficult strategy
- coding
- research
- verification
- multi-step reasoning

### ensemble
For:
- high-stakes ambiguity
- independent model comparison
- disagreement detection / verification

### future_general_intelligence
Compatibility slot only.

No current availability claim is made by this architecture.

### future_superintelligence
Compatibility slot only.

No current availability claim is made by this architecture.

## Authority rule

**Intelligence capability and execution authority are independent dimensions.**

A stronger model may be assigned a harder problem.

It does not automatically receive:
- funds authority
- destructive infrastructure authority
- commercial commitment authority
- revenue-recognition authority
- unrestricted outbound authority
- policy override authority

Control Fabric remains authoritative for action permissions.

## Model registry

Current model/provider metadata lives behind:
- `empire_os/model_registry.py`
- `config/model_registry.json`
- `empire_os/model_router.py`
- `empire_os/llm_gateway.py`

The registry may contain:
- local models
- external providers
- free-tier models
- paid models
- reasoning models
- coding/research models
- future stronger providers

Availability is not quality.

Quality priors should be replaced by Empire workload calibration as real
matched-pair evaluation data accumulates.

## Astra contract

Every Astra Executive plan step carries:
- task type
- required reasoning class
- stakes
- whether reasoning is required
- provider_pinned=false
- model_pinned=false
- future_intelligence_compatible=true
- authority_must_not_expand=true

The final provider/model is resolved only when work is executed.

## Quant separation

LLMs reason about problems.

Quant Brain performs deterministic mathematical verification.

Do not ask an LLM to become the source of truth for:
- expected economics
- risk distributions
- probability calibration
- Monte Carlo
- portfolio concentration
- value of information
- forecast scoring

The LLM may explain Quant output but must not silently alter it.

## Upgrade path

When a better model arrives:

1. discover/register it;
2. benchmark it on real Empire task classes;
3. shadow it against current models;
4. measure quality, latency, cost and failure modes;
5. verify tool-use/security behavior;
6. promote selected capabilities;
7. keep authority unchanged unless separately approved.

This applies equally to stronger local models, frontier APIs, future AGI-class
systems or future ASI-class systems.

## Current implementation

- `empire_os/intelligence_router.py`
- `empire_os/model_router.py`
- `empire_os/model_registry.py`
- `empire_os/llm_gateway.py`
- `empire_os/quant_brain.py`
- `empire_os/agi_control_api.py`
- `empire_os/astra_executive.py`

API:
- `GET /v1/agi-control/intelligence/architecture`
- `POST /v1/agi-control/intelligence/route/preview`
- `POST /v1/quant-brain/decision-packet/preview`

Current future-intelligence availability claim:
**NONE.**

The architecture is compatible with stronger systems without claiming they
exist or are deployed.
