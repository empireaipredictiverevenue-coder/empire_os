# EmpireOS — Overpass source warning, recovered & fallback-aware monitoring

20 October 2026. Source-owner issue and three-stream Core handoff.

## Original production incident

At 17:08 UTC, original `runtime/source_health/latest.json` reported
`endpoint_healthy=false`, 0 candidates and
`all requested Overpass metro queries failed` for Chicago, IL. Ops Control
reported `source_pipeline_degraded` and an acquisition warning.

Independent **bounded** network checks on the same authorised machine
confirmed failures and timeouts against multiple publicly operated Overpass
endpoints. These remote services can throttle or restrict access; do not
treat unavailable public APIs as recoverable by privilege changes or by
unbounded retries. The configured Overpass source still has no canonical
ingest authority.

The existing acquisition cycle independently succeeded at 17:34 UTC through
the original `permits` source. Its `acquisition_cycle.v2` and
`acquisition_success.v2` receipts agreed on source, timestamps and real-data
mode; `runtime_signal_inbox` receipt was present, while canonical DB
prospect writes, outreach and payments remained OFF.

At **17:39 UTC**, the existing Overpass health observer independently
reported `endpoint_healthy=true`, **5 candidates seen, 5 quality-accepted**,
no probe errors. At **17:43 UTC**, Ops Control reported `healthy=true`
with **zero blocking findings**. This recovery happened before deploying
any changes from this branch; **do not claim the code healed the public
Overpass service**. It did not authorise canonical ingestion.

## Hardening

Existing `empire_os/ops_sentinel.py` now reads the original acquisition
`last_success.json` in addition to the original acquisition and source-health
snapshots. If Overpass is unhealthy **and** a separate acquisition source
has an exact, fresh (within 45 minutes) pair of accepted source receipts,
bounded consistent 5-minute original timestamps, known source, true
original signal-inbox write and explicit no-canonical-write/no-outbound
state, the sentinel emits an informational
`source_endpoint_degraded_fallback_active` finding. It explicitly reports
the Overpass endpoint as unavailable; it never claims Overpass recovered.

When any receipt is missing, stale, forged, wrong-source, inconsistent or
shows unauthorised canonical writes/egress, the existing warning
`source_pipeline_degraded` remains active and its original reviewed repair
plan remains unchanged.

The existing Ops `acquisition_and_buyer_pipeline` health domain presents
`FALLBACK_ACTIVE_OVERPASS_UNAVAILABLE`, not a generic healthy label.
No new timer/agent, ingestion permissions, API service, source candidate
promotion, buyer tasks, CRM writes, email or payment actions.

## Operator commands

```bash
cd /srv/empire_os
PYTHONPATH=. .venv/bin/python -B -m scripts.review_founder_three_streams_20261020 \
  --read-only --format markdown

PYTHONPATH=. .venv/bin/python -B - <<'PY'
from empire_os.ops_sentinel import observe
r = observe(lambda unit: "active")
print([(x["code"], x["severity"]) for x in r["findings"]
       if x["component"] == "source_health"])
PY
```

Treat a source-only warning as an **original Source/Acquisition owner** issue
under the existing EmpireOS Core & Operations stream. Keep the broader
Revenue & Buyers goal focused on real first-party buyer enquiries and
verified orders. Do not open another general control chat for this issue.

This change supports truthful monitoring; the actual public endpoint can
fail again and no public API uptime is guaranteed.
