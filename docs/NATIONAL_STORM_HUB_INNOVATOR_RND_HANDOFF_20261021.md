# Empire AI — Existing Innovator + Supervisor → R&D Integration

**Date:** 2026-10-21
**Branch:** `feature/rd-innovator-integration-20261021`
**Classification:** Isolated source change and read-only R&D review; not a live agent activation or production rollout.

## Verified existing source
- `empire_os/agents/innovator_agent.py`: legacy weekly static three-proposal generator. It logs to `/root/feedback`, hardcodes revenue estimates, and calls an unverified decision "ship". Do **not** run its `cycle()` as a modern commercial approval.
- `empire_os/agents/supervisor_agent.py` and `empire_os/agents/supervisor.py`: old container/PM2 self-healing scripts that can restart processes. Do **not** invoke as part of R&D intake.
- `empire_os/departments.py`: canonical `rd_innovation` department and existing `strategy` Supervisor role.
- `docs/RD_DEPARTMENT_BLUEPRINT.md`: Product Innovation Lab and IDEA → RESEARCH → HYPOTHESIS → PROTOTYPE → EVALUATION → SHADOW → VALIDATED → TRANSFER_READY sequence.

## What this integration does
1. Adds **innovator** as an existing role in `rd_innovation`, not a new department.
2. Adds deterministic `empire_os/rd_innovator_review.py`. It reads founder-owned seed data and the old 3 idea names *without invoking the legacy Innovator's logging/sleep loop*.
3. Connects that passive review to the **existing** `department_cycle.py` snapshot. No new queue, timer, daemon, DB schema or API.
4. Associates the existing **Strategy Supervisor** role for review and governance only. No `incus`, PM2, restart or privilege expansion.
5. Seeds **National Storm Hub / Storm Passport / Storm Atlas** as the founder-prioritised case study, explicitly marking demand, forecast, unit economics and build/launch readiness as **unverified**.
6. Quarantines legacy `ship_action` and `expected_revenue_usdt_monthly` data. Every item remains IDEA with `execution_authority=none`.

## Local smoke check
Run only from the isolated worktree:
```bash
cd /home/ubuntu/empire_worktrees/rd_innovator_integration_20261021
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m pytest -q \
  tests/test_rd_innovator_review.py tests/test_departments.py tests/test_department_cycle.py
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -c \
  'from empire_os.rd_innovator_review import review_innovator_rd_intake; print(review_innovator_rd_intake(".")["status"])'
```

## Current bounded result
- First test suite: **10 passed**.
- Founder seed: National Storm Hub / Storm Passport / Atlas.
- Historical Innovator seeds: Empire Global Matchmaker, Empire Niche Autopilot AI, Empire AI Seller Suite.
- All proposed products require opportunity validation; none are commercial launch approvals.
- Production repo at `/srv/empire_os` has unrelated active uncommitted work; **do not overwrite or merge blindly**.

## Next R&D transfer work
- Research: test whether a ZIP-first, evidence-grounded storm dashboard is useful to homeowners.
- Technical audit: reuse current EmpireOS storm intelligence source contracts, check source licensing, data freshness and event integrity.
- Product: create offline Storm Passport and Atlas flows with synthetic fixtures explicitly labelled synthetic.
- Supervisor review: verify state/consent/privacy and separate forecast/economics from paid customer evidence.
- Only after verified benchmark/need should R&D create a `TRANSFER_READY` packet for the existing Product and Engineering owners.
- Any publishing, live customer acquisition, lead exchange, payments, system restarts or state-domain deployment needs separately scoped evidence and approvals.
