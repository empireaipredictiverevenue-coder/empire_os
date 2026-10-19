# EmpireOS — Ling 3.1 Flash Free + Scientific Agent source research

19 October 2026. Branch: `feature/predictive-decision-control-20261018`.
Existing runtime: EmpireOS ModelRegistry / ModelRouter / LLMGateway, OpenCode Zen
client, Source Intelligence, ASTRA departments, Scientific Lead Reasoning.

## Confirmed provider truth

Ling 3.1 Flash **is listed as free on OpenCode Zen**, model
`opencode/ling-3.1-flash-free` (OpenCode slug
`ling-3.1-flash-free`). Official docs:
https://docs.opencode.ai/docs/zen/

The provider marks this free availability as limited-time; a model being
catalogued or a key being present does not prove its inference service is up
or that unrestricted API automation is available.

**Read-only operational checks on 19 October:**
- Existing OpenCode Zen credentials: present (never printed).
- OpenCode CLI 1.18.31 `opencode models opencode`: lists
  `opencode/ling-3.1-flash-free`.
- Existing `OpenCodeZenClient` sent one bounded fixed public PONG prompt
  using exactly `ling-3.1-flash-free`. Received HTTP 400:
  `Upstream request failed: Model is unavailable.`
- OpenRouter advertised Ling free slug returned HTTP 404 with an explicit
  notice that its free version is not currently available there. The paid
  slug was **not** used.
- An additional capped OpenCode CLI PONG test returned no positive response
  within its 30-second timeout. That is NOT successful inference evidence.
- Other people have reported Ling-specific upstream Zen unavailability,
  including official GitHub issue anomalyco/opencode#54143.
- No £0 healthy Ling inference is verified on this EmpireOS runtime yet.
  Do not misrepresent a provider-catalogue entry as a working specialist.

## Feature-branch integration delivered

- Add `ling-3.1-flash-zen-free` to the EXISTING
  `config/model_registry.json`, provider `opencode`, exact documented free
  slug; explicitly `enabled=false`, `available=false`. Free/zero price is
  not automatically a measure of quality or availability.
- Exclude untrusted input, finance, outbound, payments, identity inference
  and automatic commercial decisions; max stakes NORMAL.
- Create `empire_os/ling31_research_readiness.py`: read-only policy and
  inference status, optional strictly one-shot public PONG probe with no
  sensitive prompts, tool access, paid fallback or automatic activation.
- Add `scientific_research_protocol()`, reusing our EXISTING
  `scientific_lead_reasoning.reason()` rather than inventing an alternative
  science agent. Seven falsification/validation controls target source
  population missingness, deduplication, original-source rights, temporal
  leakage, prequential Brier performance and independent commercial outcomes.
- Wire the Scientific Agent protocol and Ling readiness into EXISTING
  `build_revenue_stream_mining()` in Predictive Decision Control. The
  Founder Console's read-only Data Streams panel can report readiness and
  scientific controls after a coordinated backend/UI release.
- Prepare fixed, no-tools, zero-budget structured research briefing for
  eventual scientific and OpenManus specialist use. **No OpenManus executable,
  deployment status or working source-tool adapter was verified in this
  canonical feature worktree**. The brief does not claim agent execution.

Crucially, published source records may support that public data exists for
research. They CANNOT by themselves support a calibrated paid-buyer
conversion forecast or causal effect. Missing public-source data is NOT
proof that commercial demand is absent. Therefore:
- the source-reasoning indicator is only a heuristic review priority;
- `posterior_probability` is NULL;
- `control_results_verified` is false;
- no probabilities, buyer intent or expected revenue are fabricated.

## Manual read-only operator verification

```bash
cd /home/ubuntu/empire_agents/predictive_decision_control_20261018

# No external inference, no secrets printed and no payments:
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_ling31_scientific_research_20261019

# OPTIONAL, one literal public health-test prompt via Zen free slug:
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_ling31_scientific_research_20261019 \
  --probe-free-zen
```

The optional probe is never scheduled. It does not change the registry,
authorize payment or send production research data. If an inference probe
later succeeds, **that only proves health**; the Scientific Agent must still
benchmark blinded source-question accuracy, hallucination rate,
citation accuracy, semantic dedup correctness, prompt injection resistance,
latency/cost, and OpenCode retention terms BEFORE proposing activation.

The free hosted model may be subject to provider data-use/training terms.
Do not transmit private buyer/CRM, lead names, tenancy records, credentials,
copyright-restricted data or other sensitive business content to it.

## Production boundary

This feature-branch change has NOT been merged or deployed to production;
no model serving, OpenManus processing, ASTRA external research, paid
provider, data stream polling, buyer creation or economic memory mutation
was enabled. The existing local model and other validated routes remain
unmodified.
