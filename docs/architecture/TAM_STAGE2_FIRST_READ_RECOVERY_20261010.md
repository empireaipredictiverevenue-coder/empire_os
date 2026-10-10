# TAM Stage 2 — First-read failure recovery, 10 October 2026

## Production observation

The founder ran the approved Stage-2 one-shot. It verified the Stage-1 backup, isolated database catalog, took a fresh globals backup and enabled the new TAM SCRAM login. The systemd service **failed before making any database market query**, at `load_tam_isolated_dsn()` with `ValueError: missing or unsafe isolated TAM credential`. Service invocation: `1f49cd0c08b747ffb81beabda1206b06`; timestamp 2026-10-10T16:27:15Z. The script reported `TAM_STAGE2_RESULT=BLOCKED reason=FIRST_ISOLATED_TAM_READ_FAILED` and `TAM_STAGE2_FAIL_CLOSED=LOGIN_DISABLED_CREDENTIAL_RETRACTED`.

Independent unprivileged host readback: the unit remained installed and failed, the private TAM output directory existed but `latest.json` was absent, and Market GPS remained healthy. A reported cleanup is **not** independently verified database catalog proof; the recovery script re-verifies dormant NOLOGIN/no-password state against the DBA catalog before creating any new secret.

## Root-cause repair

Source credentials at `/etc/empire/tam-market.dsn` remain root-private (0400). systemd LoadCredential **copies** the secret into a separate read-only file under its private per-unit credential directory; that copy can have 0444-style mode without becoming publicly accessible, because parent directory access is restricted to the unit identity. The old loader incorrectly applied the source file's strict mode rule (no group/other readability) to the systemd delivery copy.

The repaired `empire_os/tam_isolated_credential.py` accepts a read-only delivered copy (no write bits) **only** if it arrives through `CREDENTIALS_DIRECTORY=/run/credentials/empire-tam-market-read.service`, exactly matches the TAM unit directory and that directory has no unrelated-user permissions. All arbitrary paths and non-systemd credential files continue to require owner-only file access. Symlinks, oversized/missing credential files, unexpected principals, other databases or remote hosts are still rejected. The loader does not log DSNs or secret contents.

## Recovery release and authority

`scripts/activate_empiredb_tam_stage2.sh` has a **one-time explicit recovery mode**:

```bash
cd /srv/empire_os && sudo -n bash scripts/activate_empiredb_tam_stage2.sh --recover-first-read --approved-research-only
```

**Not the original `--activate` command.** It checks that the TAM service is still in the recorded failed state with exactly the identified InvocationID, verifies its installed unit byte-for-byte matches the approved repository template, and requires stage-2 secret/scope/snapshot absent. It then verifies the stage-1 backup hashes and the live NOLOGIN/null-password restricted SQL catalog contract, checks PostgreSQL loopback password rules, backs up global roles, generates a **fresh** private credential, provisions **only** the isolated role, resets the specific failed unit and invokes the on-demand reader once. It does not overwrite/reinstall the existing unit.

The existing fail-closed EXIT handler attempts to disable the TAM role, clear its password and remove newly created secret/scope files on failure. It does not delete a possibly useful failed systemd unit or tamper with working Market GPS.

The same approved bounded scope remains GB/US roofing, solar, insurance; at most 1000 globally sampled source rows, no inferred TAM population, no outbound, no payments, no scheduler, no customer-tenant read authority.

**Testing is not activation.** Wait for real `TAM_STAGE2_RESULT=ISOLATED_RESEARCH_READ_LIVE_OBSERVE_ONLY`, inspect actual canonical counts, and verify Radar and founder view. If recovery fails, do not run it again; inspect actual unit log and safety readback first. Never print credential contents.
