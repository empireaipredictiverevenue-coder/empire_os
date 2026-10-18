# REV052 — production authenticated evidence reader verified

**18 October 2026 | Founder terminal evidence | EmpireDB | Read-only verification**

Founder ran this exact reconciliation on the canonical EmpireOS host:

```bash
cd /srv/empire_os
sudo timeout --signal=INT --kill-after=5s 40s \
  ./.venv/bin/python -B -m scripts.review_rev052_committed_login_readonly_20261018 --read-only
echo "EXIT_CODE=$?"
```

The resulting **production terminal status** was:

```text
status=REV052_EXISTING_RESTRICTED_LOGIN_VERIFIED
failure_stage=NONE
EXIT_CODE=0
```

The report returned **all 16 catalogue booleans true**, including:
hardened dedicated SCRAM LOGIN; exact only-role membership
(INHERIT FALSE, SET TRUE, ADMIN FALSE); one active trusted founder tenant
binding; existing SECURITY DEFINER read function and EXECUTE permission;
no extra login memberships; no direct SELECT on commercial events,
fulfilment orders, or buyers; valid exact local SCRAM HBA; no HBA parse errors.

All authenticated read-session booleans required for the proof were true:
SCRAM connection, exact session identity, controlled SET LOCAL ROLE, function
EXECUTE privilege, and zero-result sentinel UUID invocation.
The independent financial-table ACL proof was an administrator-only
`BEGIN READ ONLY` catalogue inspection, *not* an unprivileged table query.

The returned diagnostic explicitly stated:
`real_event_selected=false`,
`real_financial_events_read=0`,
`customer_report_release=false`,
`production_writes=false`,
`read_only=true`,
`password_printed=false`,
`mode=OBSERVE`.
A known-absent UUID yielding zero means only that authenticated function
execution worked; **it is not evidence of zero revenue**.

## Closed now

- REV051 installed the restricted NOLOGIN role and single-event read function.
- REV052 created one dedicated founder-tenant-bound SCRAM LOGIN. The original
  mutation committed once and was *not rerun* after verifier failures.
- The `fca84b1e` source fix verified the existing committed login even with
  no USAGE on private financial-table schema names (isolated hardened fixture).
- This founder-provided production readback now confirms the authenticated
  restricted login and function work on the actual EmpireDB host.

## Still open / evidence hold

- First actual pre-existing `revenue_recognized` event chosen and validated
  through the authenticated tenant-bound function.
- Real payment settlement/receipts, reversals, contracts, fulfilment and
  realised gross profit.
- Complete daily census, trustworthy forecast-vs-actual calibration, customer
  entitlement and customer financial reporting.
- Independent off-node physical recovery (separate DR programme).

## Next step (no new infrastructure)

Reuse `empire_os/predictive_revenue_canonical_reader.py` and the existing
restricted credential to review **one** legitimately existing, same-tenant
event UUID. Do not generate synthetic production transactions, select bulk
financial records, or infer daily revenue from one event. Require explicit
event scope and keep `mode=OBSERVE`; use a bounded metadata-only
candidate-discovery stage first if the genuine event ID is not yet known.

This receipt was recorded from the founder's actual production command
output. It does not represent a second live run by the agent or any new
database change. Other agents' dirty worktree files remain untouched.
