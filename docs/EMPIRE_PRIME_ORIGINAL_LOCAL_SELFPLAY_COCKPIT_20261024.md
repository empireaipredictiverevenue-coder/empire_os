# Original EmpireOS / PRIME / Digital Twin — Local Self-Play & Founder Cockpit

24 October 2026 · isolated research branch only · original production **unchanged**

## Goal and product location

Build on the **original** EmpireOS Digital Twin Phase 14, Account/Buyer Twin, PRIME objection/response/lifecycle research and physics/fractal simulator, not a new agent hierarchy or platform. The owner-facing surface uses the **existing** Search Command Centre Founder Console and the **existing loopback-only** Founder Dashboard read API. No new model service or canonical database.

## Implemented local-model research bridge

- `empire_os/digital_twin_conversation_local_selfplay.py`: two separated fictional role prompts using the shared `empire_os.coder.llama_cpp_provider.LlamaCppProvider` (qwen2.5-coder:1.5b, 127.0.0.1:11435). This is **one local model running two role prompts**, not two independent learned human digital twins.
- Fictional seller model may only propose **the pre-approved objection code**. The existing PRIME policy supplies the vetted seller text; no model-invented pricing, delivery, claims or promises are treated as approved copy. Fictional buyer generates a bounded reply; all outputs must be strict single-field JSON, no URLs, emails, personal details, instructions for sends or unverified commercial claims.
- Calls to the original `review_synthetic_conversation_loop()` before and after every model proposal. Hard caps: five turns, four model calls, 96 default tokens per call (max 192), total output-character cap, best-effort elapsed budget and original provider per-request network timeout. A synchronous blocked callback is only bounded by its implementation's timeout: do **not** claim a hard pre-emption guarantee.
- Explicit opt-out, refusal, repeated text, absent facts, malformed model outputs and unsupported seller proposals are always HOLD or STOP. "Thanks" is not verified resolution. A fictional buyer saying its concern is resolved is **not** original provider proof.
- `scripts/rehearse_prime_local_model_selfplay_20261024.py` is a **manual one-shot research-only** local inference CLI with allowlisted fictional cases, no background schedule, no API exposure and no external source. The read-only cockpit never calls this script.
- `cockpit_selfplay_shadow()` strips fictional text, never converts simulated states into a sales conversion or real-world accuracy.

### Real original local-model probe (not synthetic-test mock)

A health check to the original loopback llama.cpp server returned **healthy**.

Two constrained fictional probes were performed, neither satisfying the required completion:
1. The full seller-selection synthetic self-play probe stopped after **one inference call**, with `SELLER_MODEL_OUTPUT_HOLD`; no buyer or seller generated exchange admitted.
2. A simpler local-only request (45 output tokens and 20-second deadline) returned `llama_cpp_request_failed:TimeoutError`.

**Status: LIVE LOCAL MODEL GENERATION NOT VERIFIED; must remain on HOLD.** These were read-only inference attempts (not emails or model changes), not a successful autonomous interaction, not seller-approved output or meaningful buyer response. No fabricated passing conversation is claimed.

For a future independently authorised performance owner: inspect the existing llama.cpp runtime's performance, queues and context length, compare a smaller model request, and record a real successful, deterministic, bounded synthetic exchange before enabling any interactive local-model button. No restarts or production tweaks were made here.

## Existing Founder Console cockpit — research implementation

- `empire_os/prime_digital_twin_cockpit.py`: safe, synchronous, deterministic read model exposing one fictional dialogue, loop guard state, depth-0/1/2 fractal paths, transport latency/loss and HOLD reasons. It also shows aggregate existing 16-case / 112-node synthetic baseline, which is not buyer evidence.
- `empire_os/founder_prime_digital_twin_cockpit_api.py`: GET-only `/v1/founder-dashboard/prime-digital-twin` with strict scenario allowlist and bounded depth. It is registered only in the feature branch of existing `founder_dashboard_service.py`. POST is unsupported. It never reads provider customer data or starts inference.
- `apps/search-command-centre/src/lib/founder-api.ts`: existing server-only API helper extended, with typed response and escaped allowlisted query values.
- `apps/search-command-centre/src/app/founder/prime-digital-twin/page.tsx`: original Founder Console page with interactive GET scenario/depth selectors, fictional transcript, status cards and fractal stress/hold explorer; original Founder landing page has a navigation link. The UI is branded as research-only and never claims commercial activation.
- **Private access-control gate remains outstanding.** Search Command Centre is not itself proof of authentication; no owner ingress/auth review or user acceptance has occurred. **Do not publish this route** to an unauthenticated origin or assume production private access without a verified original network/access control.

## Tests and reproducibility

```bash
cd /home/ubuntu/empire_worktrees/prime_universal_evidence_fusion_20261024
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m pytest -q tests/test_digital_twin_local_selfplay.py tests/test_prime_digital_twin_cockpit.py

# Fictional manual local-model research only, not a buyer test:
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  scripts/rehearse_prime_local_model_selfplay_20261024.py \
  --scenario pricing_resolution --max-calls 2 --max-turns 3

# Existing deterministic original Digital Twin:
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  scripts/rehearse_prime_conversation_digital_twin_20261024.py --all --fractal-depth 2
```

All source data in code/tests is fictional. Tests use stubbed local chat callbacks, validate refusals/stalls, control budgets and prove Founder GET never activates live inference. Original local-model health and timeout evidence was checked separately, not counted as synthetic-test success.

## Release path (original owners)

1. Original Digital Twin/Model owner: establish a **successful** local synthetic end-to-end completion within measured inference and hard termination budgets. Fix performance without competing for other production workers.
2. Original Science/Quant/PRIME owner: establish held-out tests and independent scoring; neither scripted outcomes nor model-generated fictional agreement counts as real-world performance, accepted terms or a paid order.
3. Original Chief of Staff / ASTRA / Founder Console / Identity / Security owner: review the route, UI, network exposure, authentication, device/mobile accessibility and private access before any release.
4. Original Data Cloud / Conversation OS / EmpireDB owner: if real conversations are ever proposed, independently verify source rights, permitted purpose, tenant/user identity, original provider receipts, suppression, retention, durable replay and rollback gates. These are not satisfied by this research.
5. Production acceptance: full original owner security review and regression on the deployment candidate; this branch may not merge/deploy itself.

No new database, no scheduled inference, no model-weight mutation, no real buyer contact processing, no outbound, no trade, no payment and no claimed realised revenue.

**One EmpireOS. One Original Digital Twin. One PRIME. One original EmpireDB and Smart CRM.**


## Verified engineering result at handoff

- **948 affected original Digital Twin / PRIME / Conversation OS / Founder API / CRM / source authority / Quant tests passed**, with one inherited Starlette/anyio deprecation warning. This is a scoped regression, **not a full repository gauntlet**.
- Existing Search Command Centre TypeScript compilation `./node_modules/.bin/tsc --noEmit -p tsconfig.json` **passed** from this research worktree, using a read-only symlink to the existing installed dependencies. No NPM package change or dependency installation.
- The original Founder API `GET /v1/founder-dashboard/prime-digital-twin` passed TestClient requests for different fictional cases and depths; it rejects unknown cases and does not permit POST or inference.
- The manual local llama.cpp health check returned true, while actual local model requests failed to produce an accepted strict JSON result and a smaller request explicitly timed out after 20 seconds. No successful local-model two-role exchange is claimed.
- No publication, production reload, original source-owner signoff, real buyer communication, commercial conversion or actual revenue occurred.
