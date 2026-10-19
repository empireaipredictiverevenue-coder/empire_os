# EmpireOS Predictive Revenue — UK Tender Checkpoint Durability Enhancement

19 October 2026 | Branch: feature/predictive-decision-control-20261018

This continues the V2 incremental official UK procurement miner from commit
db276bac, not a new ingestion service, CRM, data lake or scheduled worker.

## Improvements delivered

### Durable previous checkpoint and safe failure mode
- Before replacing a valid current checkpoint, the system writes a copy of
  the **previous validated generation** in the existing private source
  directory, file permissions 0600.
- Both staged file contents and directory rename metadata are fsynced before
  returning success. This reduces power-loss exposure but does not make
  storage physically indestructible.
- The active file is checked before writing another generation. A corrupt
  primary is never allowed to overwrite the only known-good backup.
- The previous generation is a **recovery point**, not independently
  authenticated, cryptographically signed evidence. Administrators with
  write access can alter both files, so checksums and local filesystem
  permissions do not establish external custody.
- Health explicitly distinguishes a missing/invalid active checkpoint with
  a structurally validated backup; it does not automatically roll backward.
- The manual-only recovery entry point preserves corrupt original bytes
  in a separate private forensic file, verifies the backup again while
  holding the same source lock, and restores only if the active checkpoint
  is not healthy. It explicitly requires replaying previously observed
  windows, rather than promoting an old high watermark.

### Capacity planning / ingestion transparency
- The health object exposes remaining source receipt capacity out of 1200,
  pending internal sector reviews capacity out of 100, backup availability,
  backfill lag, and a specific suggested next safe operator action.
- At 90% completed-receipt usage, retention review is surfaced *before*
  the existing fail-closed hard cap is reached. This release deliberately
  does **not** silently prune source receipt identities, because doing so
  could mislabel replayed records as entirely new buying opportunities.
- Founder Console schema and panel have matching read-only fields.
  No production Founder Console release is performed by this branch.

### Tests / observations
- Unit tests simulate checkpoint rename failure, unsafe active corruption,
  valid previous-generation recovery, refusal to overwrite healthy active
  state, retaining corrupt bytes, refusal to advance on bad source content,
  no duplicate outbound work, and hard-cap advance notice.
- Wider affected regression: 243 Python tests, TypeScript and ESLint green.
- One explicitly requested private, bounded official-source update succeeded:
  latest four-hour partition contained zero new releases; no researched
  sector candidates were fabricated. Current V2 checkpoint still contained
  11 unique official release receipts, was 144.3 hours behind the safe
  current update window, and had 1189 free receipt slots.
- A validated previous-generation file of 2800 bytes, permissions 0600,
  was actually created beside the active checkpoint in the isolated feature
  worktree; no EmpireDB tables, production service or finance/outbound
  components were modified.

## Operators: existing feature branch only

Read checkpoint and recovery readiness with no network:
`PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m scripts.scan_uk_tender_incremental_20261018 --checkpoint-health`

Continue ONE explicit bounded public-source page and write PRIVATE checkpoint:
`PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m scripts.scan_uk_tender_incremental_20261018 --stage-private-checkpoint`

For a corrupted/missing active checkpoint with a validated previous copy
ONLY, use the manual local recovery command:
`PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m scripts.scan_uk_tender_incremental_20261018 --recover-private-checkpoint`

**Do not use manual recovery as routine maintenance, do not delete forensic
records without review, and do not convert completed source partitions into
buyer/contract/revenue claims.** Production remains untouched. A future
hardening wave should add an independently held source-change journal,
trusted source-custody attestation and a bounded retention policy before
commercial production scheduling.
