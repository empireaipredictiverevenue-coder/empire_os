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


## Source-bounded run diagnostics extension

The existing on-demand `--read-only` command also reads microsecond-resolution systemd monotonic start/exit timestamps. `materializer_last_run.duration_ms` is now based on that clock, and stays `null` when the exact duration is unavailable instead of reporting a misleading zero.

The `materializer_journal_24h` section counts **visible** verified-looking systemd closeout messages from `journalctl` over a rolling 24-hour window. The inspection accepts only bounded JSON lines attributed to PID 1 / systemd / this original unit. It has a maximum sample of 1,024 journal entries and explicitly flags when that sample limit is reached. This is **not** a complete historical service SLA, an independently authenticated business outcome or evidence of model quality. Historical success/failure totals stay uninstrumented.

A missing, malformed, inaccessible or excessive journal sample produces `null`, not invented zeroes. No unit, timer, database or inference worker is changed. The script does not install itself as a timer or activate any execution authority.
