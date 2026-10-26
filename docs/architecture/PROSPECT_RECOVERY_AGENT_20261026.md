# EmpireOS Prospect Recovery Agent — 26 October 2026

## Single mission owner

Agent ID: `empire_prospect_recovery`.

Purpose: continuously recover the historical 33K+ prospect backlog via the
existing EmpireDB v2 qualification, historical 10+5 backfills, Omega 2,
Cortex evidence review, Commercial Exchange, Buyer Acquisition Team
and Buyer Scout. Do not create a new scoring engine, database, buyer bot,
email sender, payment rail, or tenant account.

## Autonomous actions

Every 15 minutes the root-owned standalone *oneshot*:
1. Reads the five bounded, non-contact runtime receipts and validates timestamps.
2. Records absolute EmpireDB census (not the Exchange's 200-row sample), backlog,
   cursor positions, score/identity coverage, overflow, buyer research and deltas.
3. Builds a ranked, capped 12-corridor recruitment worklist using the real buyer
   team's `demand_gap_queue`. Existing Buyer Scout owns research and reconciliation.
4. Detects stale qualified/prospect/Exchange/buyer receipts, and only when stale
   requests a start of an **existing** systemd service by exact allowlisted name:
   `empire-qualification.service`,
   `empire-commercial-exchange.service`,
   `empire-buyer-acquisition-team.service`, or
   `empire-buyer-acquisition-scout.service`.
   Up to two per run; 30–100 minute cooldown. This is a start request,
   not proof the underlying job succeeded.
5. Writes a current aggregate receipt and private cooldown state.

The qualification timer remains the single DB writer and currently executes
10 chronological + 5 existing-identity historical prospects per cycle.
Evidence, site research, company association and the Omega/Cortex results are
owned by their existing workers, not performed twice here.

## Exact evidence boundaries

- The 33K population is canonical EmpireDB, not a Supabase instance.
- `v2_records` includes `insufficient_evidence`; `v2_scored` is separate.
- Score, active identity, terms/capacity and payment outcomes are independently
  gated. A high Omega score never authorizes buyer allocation.
- Existing Buyer Scout can research internally, but this agent **never**
  issues emails, approves recipients, contacts companies, accepts contracts,
  activates money, changes model weights or manufactures outcomes.
- Source records with no qualified evidence must remain HOLD.
- Missing/future/corrupt receipt is not interpreted as a successful run.
- A systemctl start receipt is `START_REQUEST_ACCEPTED_NOT_COMPLETION`,
  never a claimed service success.

## Deployment safety

A root-owned, source-pinned standalone Python module is installed at
`/usr/local/libexec/empire-prospect-recovery-agent.py`. It imports
only the Python standard library and executes with isolated imports (`-I`).
The original mutable repository code is never executed as root.

State and aggregate receipts are under:
`/var/lib/empire-prospect-recovery-agent/latest.json`
`/var/lib/empire-prospect-recovery-agent/state.json`.

Systemd service: `empire-prospect-recovery-agent.service`
Systemd timer: `empire-prospect-recovery-agent.timer`.

The timer is not installed/enabled until the owner runs the reviewed
deployment script. Dry-run:

```bash
cd /srv/empire_os
PYTHONPATH=. .venv/bin/python -B -m scripts.run_prospect_recovery_agent
```

Owner-authorised activation:

```bash
sudo bash /srv/empire_os/scripts/activate_prospect_recovery_agent_20261026.sh
```

Verification:

```bash
systemctl list-timers --all empire-prospect-recovery-agent.timer
sudo cat /var/lib/empire-prospect-recovery-agent/latest.json
journalctl -u empire-prospect-recovery-agent.service -n 25 --no-pager
```

## Success measures

Population scanned + qualified records increases; unscored declines; stalled
timers are recovered with receipts; Omega/Cortex remain evidence-bound;
identity-ready Exchange inventory and true buyer capacity improve. No genuine
revenue claimed until canonical settled payment, fulfilment and revenue evidence.
