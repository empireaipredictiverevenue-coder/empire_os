#!/usr/bin/env bash
# APPROVED STAGE 2: one TAM OBSERVE read; no outbound, payments or timers.
set -euo pipefail
set +x
umask 077
fail(){ printf 'TAM_STAGE2_RESULT=BLOCKED reason=%s\n' "$1" >&2; exit 3; }
[[ $# == 2 && $1 == --activate && $2 == --approved-research-only ]] \
  || fail EXPLICIT_STAGE2_APPROVAL_REQUIRED
[[ "$(id -u)" == 0 ]] || fail AUTHORISED_ROOT_OPERATOR_REQUIRED
cd /srv/empire_os
# Ignore shell PG* overrides; privileged catalog and role actions use
# only local peer-authenticated EmpireDB on the verified PostgreSQL 18 host.
unset PGUSER PGPASSWORD PGDATABASE PGSERVICE PGHOSTADDR PGOPTIONS
export PGHOST=/var/run/postgresql PGPORT=5432
[[ "$(systemctl is-active postgresql@18-main.service)" == active ]]   || fail CANONICAL_POSTGRES_CLUSTER_NOT_ACTIVE
[[ "$(git branch --show-current)" == agent/data-cloud-wave4 ]] \
  || fail WRONG_BRANCH
for f in empire_os/tam_market_runtime.py empire_os/tam_isolated_credential.py \
 deploy/systemd/empire-tam-market-read.service \
 scripts/verify_empiredb_tam043_stage1.sql; do
  [[ -f "$f" ]] || fail RELEASE_FILE_MISSING
  git diff --quiet HEAD -- "$f" || fail UNCOMMITTED_RELEASE_FILE
done
for tool in openssl install systemctl runuser psql pg_dumpall \
 sha256sum flock git systemd-analyze; do
  command -v "$tool" >/dev/null || fail RELEASE_DEPENDENCY_MISSING
done
[[ "$(systemctl is-active postgresql@18-main.service)" == active ]] \
 || fail POSTGRES_NOT_READY
[[ "$(systemctl show empire-tam-market-read.service -p LoadState --value)" == not-found ]] \
 || fail SERVICE_ALREADY_INSTALLED
for file in /etc/empire/tam-market.dsn /etc/empire/tam-market-scope.env \
 /etc/systemd/system/empire-tam-market-read.service \
 runtime/tam_market_intelligence/latest.json; do
 [[ ! -e "$file" && ! -L "$file" ]] || fail PREEXISTING_STAGE2_STATE_REQUIRES_REVIEW
done
exec 9>/run/lock/empiredb-tam-stage2.lock
flock -n -x 9 || fail CONCURRENT_STAGE2_BLOCKED
backup=/var/backups/empiredb/tam043-stage1/20261010T161120Z
[[ -d "$backup" && -s "$backup/empiredb-before-043.dump" &&
  -s "$backup/SHA256SUMS" ]] || fail STAGE1_BACKUP_NOT_VERIFIED
(cd "$backup" && sha256sum -c SHA256SUMS >/dev/null) \
 || fail STAGE1_BACKUP_SHA_MISMATCH
printf 'TAM_STAGE2_STAGE1_BACKUP=SHA256_VERIFIED\n'
printf 'TAM_STAGE2_FULL_RESTORE_REHEARSAL=NOT_PERFORMED\n'
# Read-only live stage-1 function/roles/grants verification, no market rows.
runuser -u postgres -- psql -X -w -q -v ON_ERROR_STOP=1 -d empiredb \
 -f scripts/verify_empiredb_tam043_stage1.sql >/dev/null \
 || fail STAGE1_LIVE_CATALOG_NOT_VERIFIED
printf 'TAM_STAGE2_PREFLIGHT=ISOLATED_NOLOGIN_CATALOG_PASS\n'
# TCP loopback must demand encrypted password challenge, never trust/cleartext.
hba="$(runuser -u postgres -- psql -X -w -q -At \
 -v ON_ERROR_STOP=1 -d empiredb -c "
SELECT
 ((SELECT count(*) FROM pg_catalog.pg_hba_file_rules
    WHERE type IN ('host','hostssl','hostnossl')
     AND auth_method IN ('trust','password') AND error IS NULL)=0)::int
 ||'|'||((SELECT count(*) FROM pg_catalog.pg_hba_file_rules
    WHERE type IN ('host','hostssl','hostnossl')
     AND auth_method IN ('scram-sha-256','md5')
     AND address IN ('127.0.0.1','127.0.0.1/32','samehost','all')
     AND error IS NULL)>0)::int
 ||'|'||((SELECT count(*) FROM pg_catalog.pg_hba_file_rules
     WHERE error IS NOT NULL)=0)::int
")" || fail POSTGRES_AUTH_INSPECTION_DENIED
[[ "$hba" == '1|1|1' ]] || fail UNSAFE_OR_INCOMPLETE_TCP_PASSWORD_AUTH

base=/var/backups/empiredb/tam043-stage2
install -d -o root -g root -m 0700 "$base"
run="$base/$(date -u +%Y%m%dT%H%M%SZ)"
[[ ! -e "$run" ]] || fail BACKUP_PATH_COLLISION
install -d -o root -g root -m 0700 "$run"
runuser -u postgres -- pg_dumpall -w --globals-only >"$run/roles-before-stage2.sql" \
 || fail GLOBAL_ROLES_BACKUP_FAILED
[[ -s "$run/roles-before-stage2.sql" ]] || fail GLOBAL_ROLES_BACKUP_EMPTY
(cd "$run" && sha256sum roles-before-stage2.sql >SHA256SUMS &&
 sha256sum -c SHA256SUMS >/dev/null) || fail GLOBAL_ROLES_HASH_FAILED
chmod 0600 "$run/roles-before-stage2.sql" "$run/SHA256SUMS"
printf 'TAM_STAGE2_GLOBAL_ROLES_BACKUP=VERIFIED\n'
install -d -o ubuntu -g ubuntu -m 0700 \
 /srv/empire_os/runtime/tam_market_intelligence
scope_tmp="$(mktemp /etc/empire/.tam-scope.XXXXXX)"
cat >"$scope_tmp" <<'SCOPE'
EMPIRE_TAM_TENANT_ID=empire-platform-research
EMPIRE_TAM_ACTIVE_INDUSTRIES=roofing,solar,insurance
EMPIRE_TAM_ACTIVE_COUNTRIES=GB,US
SCOPE
chmod 0600 "$scope_tmp"
secret_tmp="$(mktemp /etc/empire/.tam-dsn.XXXXXX)"
secret="$(openssl rand -hex 32)" || fail SECRET_GENERATION_FAILED
[[ "$(printf %s "$secret" | wc -c)" == 64 ]] || fail SECRET_LENGTH_INVALID
printf 'postgresql://empire_tam_market_login:%s@127.0.0.1:5432/empiredb\n' \
 "$secret" >"$secret_tmp"
chmod 0400 "$secret_tmp"

complete=0
cleanup(){
  result=$?
  if [[ "$complete" -ne 1 ]]; then
    systemctl stop empire-tam-market-read.service >/dev/null 2>&1 || true
    printf 'ALTER ROLE empire_tam_market_login NOLOGIN PASSWORD NULL;\n' |
      runuser -u postgres -- psql -X -w -q -v ON_ERROR_STOP=1 \
        -d empiredb >/dev/null 2>&1 || true
    rm -f /etc/empire/tam-market.dsn /etc/empire/tam-market-scope.env \
      "$scope_tmp" "$secret_tmp"
    printf 'TAM_STAGE2_FAIL_CLOSED=LOGIN_DISABLED_CREDENTIAL_RETRACTED\n' >&2
  fi
  return "$result"
}
trap cleanup EXIT

# SCRAM secret via stdin, never process arguments, env or service logs.
if ! {
  printf "SET password_encryption='scram-sha-256';\n"
  printf "ALTER ROLE empire_tam_market_login LOGIN PASSWORD '%s';\n" "$secret"
} | runuser -u postgres -- psql -X -w -q -v ON_ERROR_STOP=1 \
  -d empiredb >"$run/login.stdout.log" 2>"$run/login.stderr.log"; then
  unset secret
  fail ISOLATED_LOGIN_PROVISIONING_FAILED
fi
unset secret
mv -n "$secret_tmp" /etc/empire/tam-market.dsn
mv -n "$scope_tmp" /etc/empire/tam-market-scope.env
chmod 0400 /etc/empire/tam-market.dsn
chmod 0600 /etc/empire/tam-market-scope.env
printf 'TAM_STAGE2_LOGIN=ISOLATED_SCRAM_AUTH_ENABLED\n'

systemd-analyze verify deploy/systemd/empire-tam-market-read.service \
 >"$run/unit-verify.log" 2>&1 || fail SERVICE_UNIT_INVALID
install -o root -g root -m 0644 \
 deploy/systemd/empire-tam-market-read.service \
 /etc/systemd/system/empire-tam-market-read.service
systemctl daemon-reload || fail SERVICE_RELOAD_FAILED
[[ "$(systemctl is-enabled empire-tam-market-read.service 2>/dev/null ||
 true)" != enabled ]] || fail AUTOMATIC_SERVICE_ENABLEMENT_FORBIDDEN
systemctl start empire-tam-market-read.service \
 || fail FIRST_ISOLATED_TAM_READ_FAILED
[[ "$(systemctl show empire-tam-market-read.service -p Result --value)" == success ]] \
 || fail TAM_SERVICE_FAILED
[[ "$(systemctl show empire-tam-market-read.service -p ExecMainStatus --value)" == 0 ]] \
 || fail TAM_PROCESS_FAILED

PYTHONPATH=. ./.venv/bin/python - <<'PY'
from pathlib import Path
import json
from empire_os.revenue_completion_supervisor import tam_snapshot_truth
p=Path("runtime/tam_market_intelligence/latest.json")
if not p.is_file() or p.is_symlink() or p.stat().st_mode & 0o077:
    raise SystemExit("TAM_STAGE2_PRIVATE_SNAPSHOT_MISSING")
d=json.loads(p.read_text())
if not tam_snapshot_truth(d)["available"]:
    raise SystemExit("TAM_STAGE2_CANONICAL_CONTRACT_UNVERIFIED")
if (d.get("raw_source_rows_examined",1001)>1000 or
    d.get("source_row_count",1001)>1000 or
    d.get("approved_research_countries")!=["GB","US"] or
    d.get("approved_research_industries")!=["insurance","roofing","solar"] or
    d.get("source_population_complete") is not False or
    d.get("outreach_enabled") is not False or
    d.get("execution_authority")!="none"):
    raise SystemExit("TAM_STAGE2_SCOPE_OR_AUTHORITY_VIOLATION")
if any(s.get("country_code") not in ("GB","US") or
       s.get("industry","").casefold() not in ("roofing","solar","insurance") or
       s.get("tam_entity_count") is not None for s in d["market_scopes"]):
    raise SystemExit("TAM_STAGE2_UNVERIFIED_MARKET_COUNT_OR_SCOPE")
print(json.dumps({
 "TAM_STAGE2_CANONICAL_SNAPSHOT":"VERIFIED",
 "source_rows_examined":d["raw_source_rows_examined"],
 "source_rows_retained":d["source_row_count"],
 "out_of_scope_rows_excluded":d["out_of_scope_rows_excluded"],
 "market_scope_count":d["market_scope_count"],
 "tam_estimated_from_roster":False,
 "outbound_authority":"none",
},sort_keys=True))
PY

runuser -u ubuntu -- env PYTHONPATH=/srv/empire_os \
 /srv/empire_os/.venv/bin/python scripts/build_opportunity_radar.py \
 >"$run/radar-receipt.log" 2>&1 || fail RADAR_RESEARCH_HANDOFF_FAILED
runuser -u ubuntu -- env PYTHONPATH=/srv/empire_os \
 /srv/empire_os/.venv/bin/python scripts/run_revenue_completion_supervisor.py \
 >"$run/founder-receipt.log" 2>&1 || fail FOUNDER_TAM_READBACK_FAILED
PYTHONPATH=. ./.venv/bin/python - <<'PY'
import json
from pathlib import Path
radar=json.loads(Path("runtime/opportunity_radar/latest.json").read_text())
founder=json.loads(Path("runtime/revenue_completion_supervisor/latest.json").read_text())
if not (radar["source_status"]["tam_market"].get("available") is True
    and founder["tam_runtime"].get("available") is True
    and founder["revenue_stream_portfolio"]["tam_market_evidence"].get("available") is True
    and radar.get("automatic_external_execution_allowed") is False):
    raise SystemExit("TAM_STAGE2_DOWNSTREAM_RESEARCH_CONTRACT_FAILED")
print("TAM_STAGE2_RADAR_AND_FOUNDER=RESEARCH_EVIDENCE_VERIFIED")
PY
complete=1
printf 'TAM_STAGE2_SCOPE=GB,US_roofing,solar,insurance\n'
printf 'TAM_STAGE2_TIMER=NONE\n'
printf 'TAM_STAGE2_OUTBOUND_PAYMENTS=NOT_AUTHORISED\n'
printf 'TAM_STAGE2_RESULT=ISOLATED_RESEARCH_READ_LIVE_OBSERVE_ONLY\n'
