# TAM Stage 2 — founder-approved bounded research activation

**Approval:** 10 October 2026, initial GB and US research-only scope for roofing, solar and insurance, maximum 1,000 source records. Stage 1 had already been applied with `TAM043_RESULT=STAGE1_SQL_INSTALLED_STAGE2_HELD`. No new timing loop, customer login, outbound or payments.

## Prepared activation, not yet executed by ChatGPT

The entry point is `scripts/activate_empiredb_tam_stage2.sh`, run as an authorised DBA/root operator:

```bash
cd /srv/empire_os && sudo -n bash scripts/activate_empiredb_tam_stage2.sh --activate --approved-research-only
```

Only an actual `TAM_STAGE2_RESULT=ISOLATED_RESEARCH_READ_LIVE_OBSERVE_ONLY` with a verified snapshot and healthy readback establishes stage-2 success. No simulated test or presence of an SQL file constitutes activation.

The script performs the following guarded sequence.

1. Checks the pinned existing TAM source files are committed, verifies the canonical PostgreSQL 18 service, that the new TAM unit/credential/scope/snapshot are not already present, and takes an exclusive release lock.
2. Verifies the **actual stage-1 backup** at `/var/backups/empiredb/tam043-stage1/20261010T161120Z` via SHA-256. It repeats `scripts/verify_empiredb_tam043_stage1.sql` against the live canonical database and rejects unsafe PostgreSQL TCP authentication (including trust/cleartext host rules). It also takes a fresh owner-private and SHA-256-checked global-roles backup.
3. Creates exactly one new root-private credential under `/etc/empire/tam-market.dsn` and a separate root-private `/etc/empire/tam-market-scope.env` with `EMPIRE_TAM_TENANT_ID=empire-platform-research` (research label **not an authenticated customer tenant**), `EMPIRE_TAM_ACTIVE_INDUSTRIES=roofing,solar,insurance`, and `EMPIRE_TAM_ACTIVE_COUNTRIES=GB,US`.
4. Generates a cryptographically random 256-bit secret, enables **only** `empire_tam_market_login` with SCRAM password authentication using SQL via process STDIN (not a process argument, environment variable, command output or Git). It never alters the legacy Market GPS credential or DB role.
5. Installs the already tested on-demand `empire-tam-market-read.service` under systemd, without enabling a timer. Runs **one** bounded `--refresh --limit 1000`. That runtime **first probes the new isolated database role/function**, then reads source records read-only and fail-closes on corrupt record structures.
6. The TAM runtime strictly filters records to the approved two countries and three sectors **before saving**. Excluded records do not appear in the private `0600` output. The result explicitly records how many global records were examined and excluded, and declares `source_population_complete=false`. It never treats observed coverage as a verified TAM denominator.
7. Validates the private snapshot with the Revenue Completion Supervisor's canonical provenance, freshness, role/authority and market-scope checks; the service journal prints only counts, not names/source references. Refreshes only the existing Opportunity Radar and founder views as OBSERVE.
8. If a guarded step fails after enabling the new login, an EXIT handler stops the new service and attempts to disable **only** the new TAM login (NOLOGIN, PASSWORD NULL) and remove **only** the newly provisioned credential and scope files. A partially deployed unit remains installed but not enabled; an operator must inspect the private logs and state before any retry. Never run blindly in a loop.

**Known boundary:** the source RPC selects up to 1,000 source records globally before applying the approved market filter. A count of observed companies is a sample, **not a complete sector/country census**, and absence from the first read does not prove no company exists.

## Verification and rollback

Tests for local credential isolation, source market filtering, bounded read, fail-closed invalid inputs, journal-safe receipt, authenticated function/role semantics, deployer non-root/refusal gates, legacy Market GPS regressions, Opportunity Radar and founder consumer all run without provisioning any real password or touching production.

The stage-1 SQL rollback is separate and still held. Stage-2 emergency **credential revocation** consists of stopping only the new TAM unit, disabling `empire_tam_market_login` and clearing its password under approved DBA authority, and securely retiring the new TAM secret. It must not alter the legacy Market GPS DB role or its credentials.

**Do not** claim a market size, buyer demand, verified paying buyer, business contact, realised revenue, or commercial send from this stage-2 pilot. Production truth is established only by the command's runtime evidence.
