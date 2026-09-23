# HERMES_MODEL_PREFLIGHT_SMOKE

Job: hermes-smoke-008-model-preflight
Authority: internal_write
Base branch: feature/revenue-intelligence-v2
Executed: 2026-09-23 UTC

## Isolated proposal-only execution

The resident Hermes worker was executed only inside the isolated worktree:
/srv/empire_os/runtime/hermes_control/jobs/hermes-smoke-008-model-preflight/worktree

Production repo and production runtime were treated as read-only context and were
not modified.

## Model-health preflight verified

The preflight landed in commit 0f70887b ("Preflight OmniRoute models before
launching Hermes") and was covered by commit 23c9395e ("Test OmniRoute model
health failover"). The worker now probes OmniRoute model candidates before
launching Hermes:

DEFAULT_OMNIROUTE_MODEL_CANDIDATES:
  - gemini/gemini-3.5-flash-lite
  - gemini/gemini-3.1-flash-lite
  - gemini/gemini-3.1-pro-preview
  - openrouter/openrouter/free

The probe logic (_probe_omniroute_model) sends a minimal chat/completions
request, redacts API keys from error output, and selects the first healthy
candidate. _select_omniroute_model iterates candidates until one returns HTTP
200 with a non-empty choices list; otherwise it raises HermesControlError with
all probe outcomes. The selected model replaces the previously hardcoded
"openrouter/openrouter/free" default in the isolated hermes config.

## Tests run

PYTHONPATH=<worktree> /srv/empire_os/.venv/bin/python -m pytest \
  tests/test_hermes_control.py tests/test_hermes_control_systemd.py -q

Result: 14 passed in 0.35s.

Specific verification targets:
- tests/test_hermes_control.py: PASSED
- tests/test_hermes_control_systemd.py: PASSED

No test failures; no diagnostic or fix was required.

## Confirmed non-occurrence

No live outbound, payment/fund movement, database mutation, revenue
recognition, production merge, recovery/ access, or toop/ access occurred
during this smoke. The worktree diff against HEAD is empty after execution
(git status --short clean, git diff --check passed).

## Remaining founder gate

None outstanding for this smoke task: verification targets pass, no protected
paths touched, no production writes, no external side effects.
