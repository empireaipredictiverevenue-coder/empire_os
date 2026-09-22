# Phase 3F Production Closeout

Phase 3F engineering closeout is complete when
`runtime/phase_closeout/phase_3f_latest.json` reports
`ENGINEERING_READY` or `ENGINEERING_READY_EVIDENCE_GATED`.

Production closeout additionally requires durable automation.

## Required automation

System scope:

- `empire-department-cycle.timer` — department execution + Economic Memory.
- `empire-predictive-intelligence.timer` — refresh verified-cohort predictive
  estimates directly from canonical outcome evidence every five minutes.

User scope:

- `empire-opportunity-loop.timer` — continuous opportunity discovery,
  research, normalization, Quant review and Opportunity Value.
- `empire-predictive-cloud-status.timer` — aggregate status refresh.
- `empire-founder-dashboard-api.service` — read-only Founder Console API.

The `ubuntu` user must have systemd lingering enabled so user units survive
logout and restart.

## Automation invariant

A blocked Astra work item must never be the only future trigger for a model or
learning refresh. Phase 3F production automation does not require the
GUARDED_EXECUTE Astra dispatcher; autonomy stays within the OBSERVE boundary.
Predictive Intelligence therefore has an independent timer:
when real verified commercial outcomes arrive later, the cohort is refreshed
without requiring the old blocked queue item to be reopened.

Economic Memory is refreshed by the department cycle. Opportunity Value is
refreshed by the canonical Opportunity Loop. Predictive Cloud status is
refreshed independently.

## Production verification

Run:

```bash
PYTHONPATH=/srv/empire_os ./.venv/bin/python \
  scripts/verify_phase_3f_production.py \
  --repo-root /srv/empire_os \
  --user ubuntu
```

Phase 4 may become CURRENT only after the verifier reports
`production_ready: true`.

## Carried-forward evidence dependencies

Real terminal outcomes, verified outcome-cohort thresholds and verified
time-to-revenue cohorts remain evidence dependencies. They do not justify
invented probabilities and they do not block engineering progression.

The staged predictive timing read-model migration remains a separate production
database gate and is not applied by Phase 3F production verification.
