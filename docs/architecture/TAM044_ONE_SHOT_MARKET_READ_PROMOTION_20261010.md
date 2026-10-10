# TAM044 — One-shot market-aware research read (HELD)

Date: 10 October 2026. Production migration 044 is confirmed installed from the founder's command output. No market-aware second read has occurred.

## Proven production state
The authorized deployment printed TAM044_PREFLIGHT=READ_ONLY_PASS, TAM044_BACKUP=VERIFIED_FORMAT_AND_SHA256, and TAM044_RESULT=SCOPED_FUNCTION_INSTALLED_READER_MODE_HELD. Backup: /var/backups/empiredb/tam044-scoped/20261010T165904Z. Full restore rehearsal NOT performed.

Live service readback via unprivileged inspection: TAM one-shot service remains static/inactive/success; legacy Market GPS healthy. The existing private 0600 TAM snapshot is still eight US roofing companies from the original globally sampled run. Zero published market-size estimates, buyer intent evidence or revenue.

## Prepared read switch
scripts/promote_empiredb_tam044_one_shot.sh is a distinct founder-approved one-shot action, not part of the previously approved database migration. It:
- Refuses missing approval or non-root execution, changed release files, altered/excess scope, inactive PostgreSQL, non-static TAM unit, missing/unsafe previous artifacts.
- Verifies installed 044 owner/ACL and unchanged 043/Market GPS role grants with a read-only database catalog query. No new database DDL.
- Reuses the existing private TAM credential WITHOUT reading it into the shell, copying it, changing the login or logging it.
- Stores SHA256-verified previous nonsecret scope, private TAM snapshot, Radar snapshot and founder snapshot in a private root-owned backup location.
- Adds ONLY EMPIRE_TAM_READER_MODE=scoped_v1 to the existing explicitly approved GB/US roofing/solar/insurance research scope.
- Starts the existing static TAM systemd unit ONCE. No new timer, no enablement, no generic Mailbox/Market GPS restarts.
- Validates the fresh research-only TAM sample including all six quota cells, a 1,000 record ceiling, market-scope and sector restrictions, no false market denominator, no outbound execution; refreshes only existing Radar and founder research views.
- On any failure after changing scope, attempts to restore previous config and all three snapshots, reports TAM044_READ_RESULT=FAILED_REVIEW_BEFORE_RETRY, and requires incident review rather than looping.
- On success reports only aggregate counts and TAM044_READ_RESULT=MARKET_AWARE_OBSERVE_VERIFIED.

## Separate founder gate
The one-shot research read and protected non-secret scope switch require separate explicit approval after 044 DDL (which has now completed). If approved, the authorized operator can run:

  cd /srv/empire_os && sudo -n bash scripts/promote_empiredb_tam044_one_shot.sh --one-shot --approved-scoped-research

Current Remote Commander policy does NOT allow ChatGPT to execute this privileged action. Do not claim that the scoped run is live without the actual command result. No new outbound, payment, customer login, agents, timers or invented buyer prospects are authorized.
