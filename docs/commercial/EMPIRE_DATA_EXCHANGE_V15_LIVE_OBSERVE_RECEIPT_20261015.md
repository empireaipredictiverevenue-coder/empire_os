# Empire Data Exchange V15 — Production OBSERVE Activation Receipt

**State: PRODUCTION_OBSERVE_CUSTODY_ACTIVE** (15 October 2026)
**Scope: first-party public-source observation custody ONLY**
Code commit at activation: `1b5255a1` in canonical `/srv/empire_os`.
This record is based on the founder-provided privileged operator receipt.
The unprivileged Remote Commander verified the static systemd unit and
code commit but cannot independently read the root-owned DSN or database rows.

## Verified production operator result

Operator: `scripts.recover_data_exchange_v15_partial` with the
previously approved bounded `--apply --approved-data-exchange-v15-observe-only`.

- Result: `PRODUCTION_OBSERVE_CUSTODY_ACTIVE`
- `canonical_rows=1` (ONE stored snapshot, not three observations)
- `first_sequence=0`
- `canonical_head_sha256=c7c3b13bde6684168e07fc9af17c19b8183d8b43c7de5930fa55814210ae4f1c`
- `dedicated_connect_grant_committed=true`
- `database_writes=true` (the specific CONNECT grant and capture)
- `hba_changes=false`, `password_rotation=false`
- `outbound_enabled=false`, `payment_execution=false`
- `customer_delivery_enabled=false`
- `external_anchor_verified=false`
- `source_field_rights_cleared=false`
- `actual_revenue_verified=false`
- `timer_installed=false`

The first captured observation is based on the locked three-entity
UK Planning Data brownfield pilot. **One snapshot does not establish
an observed transition, construction start, permit, buyer intent or revenue.**

## Post-activation read-only service check

From canonical Ubuntu runtime:
- `systemctl show empire-data-exchange-custody-capture.service`:
  `LoadState=loaded`, `ActiveState=inactive`, `UnitFileState=static`,
  `Result=success`, `ExecMainStatus=0`
- This is expected for a completed on-demand **oneshot** service.
- `systemctl list-unit-files 'empire-data-exchange*'` reported
  only the static capture unit, not a scheduled timer.
- Backup root existed as root-owned 0700; the unprivileged caller
  cannot read the root-owned credentials or backup content.

## Release is complete for V15 OBSERVE custody

Do not rerun the installer or partial recovery:
the table, protected roles and first canonical observation are now present.
The migration is not a standing migration to reapply.

Next substantive build is time-separated, bounded official source
observations + comparison through V14, **not** synthetic project leads.
Independent dataset rights review and commercial entitlements still
gate any buyer-facing feed. No automation or new outbound is approved.
