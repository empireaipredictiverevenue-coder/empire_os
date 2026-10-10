#!/usr/bin/env bash
# HELD: founder-gated one-shot TAM044 research promotion.
# Does NOT alter roles/credentials, restart Market GPS, or enable timers.
set -euo pipefail
set +x
umask 077
fail(){ printf 'TAM044_READ_RESULT=BLOCKED reason=%s\n' "$1" >&2; exit 3; }
if [[ $# -ne 2 ]]; then fail "EXPLICIT_ONE_SHOT_APPROVAL_REQUIRED"; fi
[[ "$1" == "--one-shot" && "$2" == "--approved-scoped-research" ]] ||
  fail "EXPLICIT_ONE_SHOT_APPROVAL_REQUIRED"
[[ "$(id -u)" == 0 ]] || fail "AUTHORised_ROOT_REQUIRED"
cd /srv/empire_os
[[ "$(git branch --show-current)" == "agent/data-cloud-wave4" ]] ||
  fail "UNEXPECTED_RELEASE_BRANCH"
for path in empire_os/tam_market_runtime.py \
  empire_os/revenue_completion_supervisor.py \
  scripts/verify_empiredb_tam044.sql \
  deploy/systemd/empire-tam-market-read.service; do
  [[ -f "$path" ]] || fail "RELEASE_FILE_MISSING"
  git diff --quiet HEAD -- "$path" || fail "RELEASE_FILE_DIRTY"
done
for utility in systemctl runuser psql flock stat install sha256sum \
    mktemp cmp cp mv; do
  command -v "$utility" >/dev/null || fail "DEPENDENCY_MISSING"
done
unset PGUSER PGPASSWORD PGDATABASE PGSERVICE PGHOSTADDR PGOPTIONS
export PGHOST=/var/run/postgresql PGPORT=5432
[[ "$(systemctl is-active postgresql@18-main.service)" == active ]] ||
  fail "CANONICAL_POSTGRES_NOT_ACTIVE"
[[ "$(systemctl show empire-tam-market-read.service -p LoadState --value)" == loaded ]] ||
  fail "TAM_SERVICE_NOT_INSTALLED"
[[ "$(systemctl show empire-tam-market-read.service -p ActiveState --value)" == inactive ]] ||
  fail "TAM_SERVICE_NOT_IDLE"
[[ "$(systemctl show empire-tam-market-read.service -p Result --value)" == success ]] ||
  fail "TAM_SERVICE_PREVIOUS_FAILURE"
[[ "$(systemctl show empire-tam-market-read.service -p UnitFileState --value)" == static ]] ||
  fail "TAM_SERVICE_NOT_STATIC"
cmp -s deploy/systemd/empire-tam-market-read.service \
  /etc/systemd/system/empire-tam-market-read.service ||
  fail "TAM_INSTALLED_UNIT_DIFFERENT_FROM_REVIEWED"
scope=/etc/empire/tam-market-scope.env
secret=/etc/empire/tam-market.dsn
tam=runtime/tam_market_intelligence/latest.json
radar=runtime/opportunity_radar/latest.json
founder=runtime/revenue_completion_supervisor/latest.json
[[ -f "$scope" && ! -L "$scope" &&
  "$(stat -c '%a:%U:%G' "$scope")" == 600:root:root ]] ||
  fail "TAM_PROTECTED_SCOPE_UNVERIFIED"
[[ -f "$secret" && ! -L "$secret" &&
  "$(stat -c '%a:%U:%G' "$secret")" == 400:root:root ]] ||
  fail "TAM_EXISTING_SECRET_UNVERIFIED"
[[ -f "$tam" && ! -L "$tam" &&
  "$(stat -c '%a:%U:%G' "$tam")" == 600:ubuntu:ubuntu ]] ||
  fail "TAM_BASELINE_SNAPSHOT_UNVERIFIED"
for path in "$radar" "$founder"; do
  [[ -f "$path" && ! -L "$path" ]] ||
    fail "DOWNSTREAM_BASELINE_MISSING"
done
exec 9>/run/lock/empiredb-tam044-one-shot-read.lock
flock -n -x 9 || fail "PARALLEL_TAM044_ONE_SHOT_BLOCKED"

# Reject any changed/expanded market scope, secret not read or echoed.
expected="$(mktemp /run/tam044-scope-expected.XXXXXX)"
trap 'rm -f "$expected"' EXIT
printf '%s\n' \
  'EMPIRE_TAM_TENANT_ID=empire-platform-research' \
  'EMPIRE_TAM_ACTIVE_INDUSTRIES=roofing,solar,insurance' \
  'EMPIRE_TAM_ACTIVE_COUNTRIES=GB,US' > "$expected"
cmp -s "$expected" "$scope" ||
  fail "EXISTING_SCOPE_NOT_EXACTLY_APPROVED"

# DB metadata only, not a commercial/market read.
runuser -u postgres -- psql -X -w -q -v ON_ERROR_STOP=1 \
  -d empiredb -f scripts/verify_empiredb_tam044.sql >/dev/null ||
  fail "LIVE_044_CATALOG_UNVERIFIED"
printf 'TAM044_READ_PREFLIGHT=SCOPED_DB_FUNCTION_VERIFIED\n'

backup_base=/var/backups/empiredb/tam044-one-shot
install -d -o root -g root -m 0700 "$backup_base"
backup="$backup_base/$(date -u +%Y%m%dT%H%M%SZ)"
[[ ! -e "$backup" ]] || fail "BACKUP_COLLISION"
install -d -o root -g root -m 0700 "$backup"
cp -p "$scope" "$backup/scope.before"
cp -p "$tam" "$backup/tam.before.json"
cp -p "$radar" "$backup/radar.before.json"
cp -p "$founder" "$backup/founder.before.json"
(
  cd "$backup"
  sha256sum scope.before tam.before.json radar.before.json founder.before.json \
    >SHA256SUMS
  sha256sum -c SHA256SUMS >/dev/null
) || fail "BASELINE_BACKUP_HASH_FAILED"
chmod 0600 "$backup"/*
printf 'TAM044_READ_BASELINE_BACKUP=SHA256_VERIFIED\n'
printf 'TAM044_READ_BACKUP_LOCATION=%s\n' "$backup"
new_scope="$(mktemp /etc/empire/.tam044-scope.XXXXXX)"
cp "$scope" "$new_scope"
printf '%s\n' 'EMPIRE_TAM_READER_MODE=scoped_v1' >>"$new_scope"
chown root:root "$new_scope"
chmod 0600 "$new_scope"

finished=0
restore(){
  src="$1"; dest="$2"
  tmp="$(mktemp "$dest.tam044-rollback.XXXXXX")" || return 1
  install -o ubuntu -g ubuntu -m 0600 "$src" "$tmp" || return 1
  mv -f "$tmp" "$dest"
}
cleanup(){
  code=$?
  if [[ "$finished" != 1 ]]; then
    systemctl stop empire-tam-market-read.service >/dev/null 2>&1 || true
    install -o root -g root -m 0600 "$backup/scope.before" "$scope" || true
    restore "$backup/tam.before.json" "$tam" || true
    restore "$backup/radar.before.json" "$radar" || true
    restore "$backup/founder.before.json" "$founder" || true
    printf 'TAM044_READ_ROLLBACK=ATTEMPTED_RESTORE_SCOPE_AND_PRIVATE_SNAPSHOTS\n' >&2
    printf 'TAM044_READ_RESULT=FAILED_REVIEW_BEFORE_RETRY\n' >&2
  fi
  rm -f "$new_scope" "$expected"
  return "$code"
}
trap cleanup EXIT
mv -f "$new_scope" "$scope"
printf 'TAM044_READ_MODE=SCOPED_V1_ONE_SHOT\n'

# Existing static one-shot unit, not restarted, enabled, or scheduled.
systemctl start empire-tam-market-read.service ||
  fail "SCOPED_SERVICE_FIRST_READ_FAILED"
[[ "$(systemctl show empire-tam-market-read.service -p Result --value)" == success ]] ||
  fail "SCOPED_SERVICE_RESULT_FAILED"
[[ "$(systemctl show empire-tam-market-read.service -p ExecMainStatus --value)" == 0 ]] ||
  fail "SCOPED_SERVICE_NONZERO_EXIT"

PYTHONPATH=. ./.venv/bin/python - <<'PY'
from pathlib import Path
import json
from empire_os.revenue_completion_supervisor import tam_snapshot_truth
path=Path('runtime/tam_market_intelligence/latest.json')
if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
    raise SystemExit('TAM044_PRIVATE_CANONICAL_SNAPSHOT_UNSAFE')
data=json.loads(path.read_text())
proof=tam_snapshot_truth(data)
expected={(i,c) for i in ('roofing','solar','insurance') for c in ('GB','US')}
coverage=data.get('market_scope_sample_coverage')
if (proof.get('available') is not True or
    proof.get('sampling_method')!='MARKET_QUOTA_SAMPLED' or
    proof.get('requested_market_scope_count')!=6 or
    data.get('requested_sample_limit')!=1000 or
    data.get('approved_research_industries')!=['insurance','roofing','solar'] or
    data.get('approved_research_countries')!=['GB','US'] or
    data.get('source_population_complete') is not False or
    data.get('source_rows_examined_meaning')!='RETURNED_SAMPLE_ROWS_ONLY' or
    data.get('source_row_count',1001)>1000 or
    data.get('out_of_scope_rows_excluded')!=0 or
    data.get('execution_authority')!='none' or
    data.get('outreach_enabled') is not False or
    not isinstance(coverage,list) or len(coverage)!=6 or
    {(x.get('industry'),x.get('country_code')) for x in coverage}!=expected):
    raise SystemExit('TAM044_SCOPED_RESEARCH_EVIDENCE_INVALID')
print(json.dumps({
    'TAM044_PRIVATE_SNAPSHOT':'VERIFIED',
    'requested_market_scopes':6,
    'observed_market_scopes':proof['market_scope_count'],
    'zero_observation_scopes':proof['market_scope_zero_observation_count'],
    'sampled_records':proof['source_row_count'],
    'market_size_claims':0,
    'outbound_authorised':False,
},sort_keys=True))
PY

runuser -u ubuntu -- env PYTHONPATH=/srv/empire_os \
  /srv/empire_os/.venv/bin/python scripts/build_opportunity_radar.py \
  >"$backup/radar.log" 2>&1 ||
  fail "RADAR_REFRESH_FAILED"
runuser -u ubuntu -- env PYTHONPATH=/srv/empire_os \
  /srv/empire_os/.venv/bin/python scripts/run_revenue_completion_supervisor.py \
  >"$backup/founder.log" 2>&1 ||
  fail "FOUNDER_REFRESH_FAILED"
PYTHONPATH=. ./.venv/bin/python - <<'PY'
from pathlib import Path
import json
radar=json.loads(Path('runtime/opportunity_radar/latest.json').read_text())
founder=json.loads(Path('runtime/revenue_completion_supervisor/latest.json').read_text())
if (radar.get('source_status',{}).get('tam_market',{}).get('available') is not True
    or radar.get('automatic_external_execution_allowed') is not False
    or radar.get('execution_authority')!='none'
    or founder.get('tam_runtime',{}).get('available') is not True
    or founder['tam_runtime'].get('sampling_method')!='MARKET_QUOTA_SAMPLED'
    or founder['tam_runtime'].get('requested_market_scope_count')!=6
    or founder.get('revenue_stream_portfolio',{})
              .get('tam_market_evidence',{}).get('available') is not True
    or founder.get('execution_authority')!='none'):
    raise SystemExit('TAM044_DOWNSTREAM_OBSERVE_CONTRACT_FAILED')
print('TAM044_RADAR_AND_FOUNDER=VERIFIED_OBSERVE_ONLY')
PY

finished=1
printf 'TAM044_READ_ONE_SHOT=VERIFIED\n'
printf 'TAM044_READ_NEW_TIMER=NONE\n'
printf 'TAM044_READ_MARKET_GPS=UNCHANGED\n'
printf 'TAM044_READ_OUTBOUND_OR_PAYMENTS_AUTHORITY=NONE\n'
printf 'TAM044_READ_RESULT=MARKET_AWARE_OBSERVE_VERIFIED\n'
