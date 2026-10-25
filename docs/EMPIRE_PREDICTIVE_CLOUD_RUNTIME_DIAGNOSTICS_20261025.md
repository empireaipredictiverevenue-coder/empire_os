# Predictive Cloud runtime diagnostics v1 (25 October 2026)

Scope: read-only measurements for the **existing** EmpireOS/EmpireDB/Cloud/Jev system. This is not a new service, timer, inference runner or financial model.

Run from the already installed environment:

```bash
cd /srv/empire_os
PYTHONPATH=. .venv/bin/python -B scripts/review_predictive_cloud_runtime_diagnostics_20261025.py --read-only
```

The report exposes the last materializer result and duration (from `systemctl show`), current host memory, repository filesystem capacity, 1-minute load divided by logical CPU count, and source-reported Cloud/Predictive/Jev snapshot ages. Snapshot timestamps are **not** the same as actual source ingestion lag, and last-run status is **not** a historical success or failure rate.

Uninstrumented fields stay explicitly `null` or appear in `not_instrumented`. A 200 response, current unit result, local snapshot, model confidence, or a source-provided matched-outcome count never proves independent verified revenue.

No journald scans, database queries or writes, paid requests, systemd restarts, new migrations, business data fixtures or payments. The diagnostic script is an on-demand read-only CLI; it has no automation or authority to promote a model.

Run deterministic acceptance:

```bash
PYTHONPATH=. .venv/bin/python -B -m pytest -q -p no:cacheprovider tests/test_predictive_cloud_runtime_diagnostics_20261025.py
```

Future work must connect historical run counts, backlog, inference latency, true ingestion lag, source failure rates and evaluation throughput to trustworthy owned telemetry before declaring those metrics available.
