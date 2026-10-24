# PRIME / Original Digital Twin — Fractal and Physics-Inspired Conversation Stress Testing

24 October 2026 | EmpireOS / Original Predictive Cloud | Research-only integration | Production unchanged

## Scope and mathematical honesty

This enhancement belongs to the existing EmpireOS Phase 14 Digital Twin and PRIME's existing Conversation OS objection-resolution lifecycle. It is NOT another simulator/agent hierarchy/CRM/database. The original Digital Twin market/Account/Buyer evidence models and original science/quant authority remain unchanged.

"Fractal" is used carefully: **recursively self-similar scenario branching** with binary branch factor b=2. The number of nodes at depth d, starting from n roots, is n × sum(2**k for k in range(d+1)). These are recursively generated test cases, NOT real conversation data and NOT a measured Hausdorff dimension of human behaviour. The synthetic simulation sets fractal_geometry_dimension=null.

"Physics" means **dimensionally consistent discrete-time communication-channel stress constraints**, not physical laws that predict emotions or personality. Each fictional message has a seeded reproducible nonnegative one-way latency plus bounded jitter, measured in milliseconds; a time-budget deadline and optional dropped messages produce a causal hold. No real physical channel was measured. Original seller explanation/call/lead/revenue truth **cannot be created from missing delivery**.

Only simulation-relevant invariants are enforced: finite turns, bounded scenario tree, nonnegative transport latency, timeout causality, dropped + delivered message count = original simulated message count, source-body quote exclusion, no opt-out follow-up, and no real-revenue promotion. Uncertainty about an actual buyer remains UNKNOWN.

## Implemented, in the original branch

- `empire_os/digital_twin_conversation_fractal_physics.py`: bounded binary-branch expansion and deterministic synthetic latency/jitter/dropout. It calls the existing original `rehearse_conversation`, which itself uses the same objection-cue and lifecycle code as PRIME. Original source-owner IDs, Gmail, CRM data, profiles and private messages are never inputs.
- Branch `L` doubles a fictional latency perturbation at each occurrence. Branch `D` introduces a dropped fictional message and quoted-history noise, verifying that spoofed old instructions are not accepted as the current person's intent. Both can be nested up to depth 3, subject to a hard 128-node cap.
- `scripts/rehearse_prime_conversation_digital_twin_20261024.py`: existing original CLI extended with `--fractal-depth`, `--channel-latency-ms`, `--channel-timeout-ms`, and `--synthetic-seed`. Its existing `--cross-sector`, `--all`, `--scenario` and `--show-synthetic-dialogue` options remain available.
- `empire_os/predictive_revenue_brain_bridge.py`: an optional `original_fractal_physics_conversation_gauntlet` input now produces `prime_original_fractal_physics_conversation_simulation`, a strict reduced simulation summary with no dialogue, private case identifiers, live source authority, revenue or model-mutation claims.
- `tests/test_digital_twin_conversation_fractal_physics.py`: reproducibility, conservation, branch growth, timeout boundary, dropped seller reply, dropped opt-out, no real-world outcome claims, source quote interference, excessive expansion refusal, forged evidence detection, cross-sector compatibility and original PRIME bridge compatibility.

## Executed offline rehearsal (real executed code, entirely fictional data)

| Scenario collection | Baseline fictional scripts | Fractal/physics nodes at depth 2 | Scripted logic failures | Expected causal/policy holds |
|---|---:|---:|---:|---:|
| Original conversation scenarios | 11 | 77 | 0 | 47 |
| Finance, logistics, travel, legal, energy | 5 | 35 | 0 | 20 |
| Both groups | 16 | 112 | 0 | 67 |

The holds are **desirable fail-closed observations** due to deliberately dropped messages or forbidden unsupported seller claims. They are NOT real failures to close sales. No simulated buyer reply, pretend payment, or theoretical physics quantity is counted as a real-world result.

Reproduce without external services:

```bash
cd /home/ubuntu/empire_worktrees/prime_universal_evidence_fusion_20261024

PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  scripts/rehearse_prime_conversation_digital_twin_20261024.py --fractal-depth 2

PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  scripts/rehearse_prime_conversation_digital_twin_20261024.py \
  --all --fractal-depth 2

# A deliberately tight hypothetical transport deadline:
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  scripts/rehearse_prime_conversation_digital_twin_20261024.py \
  --fractal-depth 2 --channel-latency-ms 500 --channel-timeout-ms 800
```

All original CLI output is source-marked SIMULATION. A five-turn conversation is the maximum and branch/root caps prevent runaway recursion. The synthetic dropout branch deliberately prevents "seller replied" → "person confirmed" false closure. The Founder summary rejects a parent or child simulation packet that claims authenticated buyers, sent messages, actual revenue or model-weight learning.

## What remains before claiming anything about customers

1. **Autonomous self-play is still absent.** This stage is deterministic two fictional roles plus scripted reactions, not local LLM-versus-LLM conversation or independently generated real-world behavioural data.
2. The Channel/latency assumptions are invented **stress-test parameters**. Calibrate only to genuine permitted operational metrics if original Security/Privacy/Data Cloud/Conversation OS owners provide permission and data rights. Do not infer emotional friction, psychological susceptibility, personality or conversion probability.
3. Add distinct held-out paraphrases, multilingual objections, code-switching, interrupted dialogues, unsupported commercial terms and counterexamples. Preserve negative outcomes, opt-outs, silence and refusal without training the system to overcome consent.
4. If original owners approve local-model fictional self-play, first isolate input/output, hold budgets, require human evaluation and compare scenario outcomes against blinded expected behaviour. Do not train on private customer texts or silently reuse real message corpora.
5. True external validity requires independently authenticated future partner/customer interactions, voluntary permissioned use, held-out outcome evaluation and quant calibration. Neither 11/11 script passes nor 112 recursive nodes prove predictive accuracy, real-world objection resolution, contract conversion or revenue.
6. Only original Core/Chief of Staff/ASTRA, Conversation OS, Digital Twin, Science/Quant, Data Cloud, EmpireDB and Security owners can approve merge/deployment. No canonical production checkout, database, email sender, trades, money, or customer records were modified by this research work.

## Test status

**874 original Digital Twin / PRIME affected-contract scoped regression tests passed** on the research worktree, with one inherited Starlette/anyio deprecation warning. The cross-sector 5-scenario CLI and the combined 16-scenario CLI were run independently with depth-2 outputs 35 and 112 respectively, with zero scripted logic-contract mismatches. This is NOT a whole-repository suite, not autonomous self-play, not real-world validation, and not an original source-owner production release approval.

One EmpireOS. One original EmpireDB. One Smart CRM. One existing Digital Twin and Predictive Cloud/PRIME.


## 24 October — Explicit anti-loop release guard, finished before next build

The original `digital_twin_conversation_rehearsal.py` now owns `review_synthetic_conversation_loop()` and calls it in every synthetic conversation. It is **not** another service or AI agent.

- Five-turn cap (smaller caller budgets allowed). Overbudget continuation returns `TURN_BUDGET_EXCEEDED_HOLD` and is not scored as an acceptable scenario.
- Repetition guard compares bounded, normalized **current** synthetic utterances, role by role, while excluding quoted historical content. Repeated fictional buyer questions or fictional seller pitches produce `REPEATED_TURN_STALLED_NEEDS_REVIEW`; no indefinite conversational cycling.
- Fictional STOP, unsubscribe or clear refusal means no further model-generated/seller response. Any message after STOP produces `POST_STOP_MESSAGE_HOLD`. STOP itself is terminal, not a request to overcome an objection.
- Non-synthetic actor/provenance flags, extra private fields, empty/current-invalid turns and malformed budgets fail closed. The watchdog returns **codes, not transcript text**. It never grants access to source messages or sends any email.
- The existing `digital_twin_conversation_fractal_physics.py` now directly inherits the watchdog: a stalled conversation adds a hold reason, cannot be treated as a causally complete delivered conversation, and exposes only an aggregate stall count through the existing PRIME Founder bridge. Parent/child output tampering and forged stall totals are rejected.
- This only guards the **existing deterministic scripted simulator**. There are no ongoing autonomous model calls yet. An independently approved future local-model adapter must additionally enforce timeout, maximum *inference calls*, maximum output tokens and explicit stopping after `STALLED_NEEDS_REVIEW`; the present code must not claim to have tested an unbuilt autonomous model.

Verification: **900 scoped original Digital Twin, PRIME, Conversation OS, Quant, CRM and signed-owner contract tests passed**, with one inherited Starlette/anyio deprecation warning (not a full repository gauntlet). Existing 16 fictional scenarios still expand to **112** bounded fractal/physics nodes, reporting **zero stalled turns** and **zero predefined script-contract mismatches**. Separate adversarial tests deliberately generate STOP, repetition and overbudget failures and verify mandatory holds.

**Stop/exit criterion for this engineering milestone:** watchdog implemented, failure modes adversarially tested, original 112-node simulation preserved, code committed to the isolated research branch. Do **not** reopen endless synthetic self-reassurance tests. Resume the founder's original Digital Twin/physics objective: budgeted, purely fictional local-model buyer/seller self-play with independent expected-outcome evaluation before any permitted real-world shadow validation.

No production checkout, original EmpireDB, Smart CRM, mail transport, real buyer, money or inference-model weights modified.
