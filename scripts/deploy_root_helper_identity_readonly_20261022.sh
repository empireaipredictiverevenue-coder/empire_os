#!/usr/bin/env bash
# Owner-reviewed protected release, unchanged original privileged RPC.
# Default is READ-ONLY. --apply-founder-approved is a separately gated step.
set -Eeuo pipefail
OLD=/opt/empire-ai/privileged-helper/releases/20261015-custody-audit-v5
CAND=/home/ubuntu/empire_releases/root_helper_agent_identity_candidate_20261022
NEW=/opt/empire-ai/privileged-helper/releases/agent-identity-readonly-20261022v1
DROP=/etc/systemd/system/empire-ops-privileged-helper.service.d/95-agent-identity-readonly-20261022.conf
UNIT=empire-ops-privileged-helper.service
OLD_SHA=3d2d66c17c09900864eef3ca6776af0456269c655479c8d615c6762c566ec239
CAND_SHA=20624ba83d1a8797d3ad649f947ec6fbf2619b66e6d2863e4c211246ba54f64e
MANIFEST_SHA=938a397a4157685912dfd50b2dcd2ce0a670aa732ee43d94eae904c55dbea436
IDENTITY=/run/empire-ops/agent-identity-readonly.sock
LEGACY=/run/empire-ops/privileged.sock
STEP=preflight
DROP_CREATED=0

die() { echo "ROOT_HELPER_IDENTITY_RELEASE_HOLD: $*" >&2; exit 1; }
override_contents() {
  printf '[Service]\nWorkingDirectory=%s\nEnvironment=PYTHONPATH=%s\nEnvironment=PYTHONNOUSERSITE=1\nEnvironment=PYTHONDONTWRITEBYTECODE=1\nExecStart=\nExecStart=/usr/bin/python3 -B -P -m empire_os.ops_privileged_helper --socket /run/empire-ops/privileged.sock --allowed-user ubuntu\n' "$NEW" "$NEW"
}
verify_files() {
  local root="$1"
  printf '%s  %s\n' "$MANIFEST_SHA" "$root/CHECKSUMS.sha256" | sha256sum --check --status
  printf '%s  %s\n' "$CAND_SHA" "$root/empire_os/ops_privileged_helper.py" | sha256sum --check --status
  python3 -B - "$root" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])
expected={"90-root-owned-helper.conf","CHECKSUMS.sha256",
          "empire_os/__init__.py","empire_os/data_cloud_runtime_health.py",
          "empire_os/ops_privileged_helper.py","empire_os/agent_peer_identity.py",
          "empire_os/agent_identity_root_adapter.py"}
assert root.is_dir() and not root.is_symlink()
assert {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()} == expected
assert not any(p.is_symlink() for p in root.rglob('*'))
PY
  (cd "$root" && sha256sum --check --status CHECKSUMS.sha256)
}
legacy_canary() {
  /usr/bin/python3 -B - <<'PY'
import json,socket,sys
s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
s.settimeout(5)
try:
 s.connect("/run/empire-ops/privileged.sock")
 s.sendall(b'{"request_id":"agent-identity-preserve","action":"service_status","unit":"empire-public-gateway.service"}\n')
 raw=s.recv(8192)
 doc=json.loads(raw)
 if doc.get("request_id")!="agent-identity-preserve" or doc.get("action")!="service_status":
  sys.exit(1)
finally:
 s.close()
PY
}
identity_denial_canary() {
  /usr/bin/python3 -B - <<'PY'
import json,socket,sys
p="/run/empire-ops/agent-identity-readonly.sock"
s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
s.settimeout(5)
try:
 s.connect(p)
 ready=s.recv(1024)
 if ready != b'EMPIRE_AGENT_IDENTITY_READY_V1' + bytes((10,)):
  sys.exit(1)
 s.sendall(b'{"op":"identity_preflight","agent_id":"empire_coder","nonce":"only_unmanaged_probe_abcdef"}'+bytes((10,)))
 raw=s.recv(8192)
 if not raw: sys.exit(1)
 doc=json.loads(raw)
 if doc.get("ok") is not False or doc.get("signing_key_issued") is not False:
  sys.exit(1)
finally:
 s.close()
PY
}
preflight() {
  [[ -d "$OLD" && -d "$CAND" && -S "$LEGACY" ]] || die "release_or_live_rpc_missing"
  [[ ! -e "$DROP" && ! -L "$DROP" ]] || die "owned_override_already_exists"
  [[ "$(systemctl show "$UNIT" -p WorkingDirectory --value)" == "$OLD" ]] || die "current_unit_not_original_pinned_release"
  [[ "$(systemctl show "$UNIT" -p ActiveState --value)" == active ]] || die "protected_root_helper_not_active"
  [[ "$(systemctl show "$UNIT" -p User --value)" == root ]] || die "protected_unit_not_root_owned"
  printf '%s  %s\n' "$OLD_SHA" "$OLD/empire_os/ops_privileged_helper.py" | sha256sum --check --status || die "original_helper_hash_changed"
  verify_files "$CAND" || die "candidate_digest_or_inventory_mismatch"
  if [[ -e "$NEW" || -L "$NEW" ]]; then
    verify_files "$NEW" || die "protected_staged_release_changed"
    [[ "$(stat -c '%u' "$NEW")" == 0 ]] || die "protected_release_not_owned_by_root"
  fi
  legacy_canary || die "existing_management_socket_failed"
  [[ ! -e "$IDENTITY" && ! -L "$IDENTITY" ]] || die "unexpected_existing_identity_socket"
  echo "ROOT_HELPER_IDENTITY_DRY_RUN_PASS; running root helper unchanged"
}
rollback_once() {
  local code="$1" phase="$2"
  trap - ERR
  set +e
  echo "ROOT_HELPER_IDENTITY_ACTIVATION_FAILED step=$phase exit_status=$code" >&2
  if [[ "$DROP_CREATED" == 1 ]]; then
    if [[ -f "$DROP" ]] && cmp -s "$DROP" <(override_contents); then
      rm -f -- "$DROP"
      systemctl daemon-reload
      systemctl restart "$UNIT"
      if [[ "$(systemctl show "$UNIT" -p WorkingDirectory --value)" == "$OLD" ]] && legacy_canary; then
        if [[ -S "$IDENTITY" && ! -L "$IDENTITY" ]]; then rm -f -- "$IDENTITY"; fi
        echo "ROOT_HELPER_IDENTITY_ROLLED_BACK_TO_ORIGINAL" >&2
      else
        echo "ROOT_HELPER_ROLLBACK_REQUIRES_OPERATOR_REVIEW" >&2
      fi
    else
      echo "OVERRIDE_CHANGED_EXTERNALLY_DO_NOT_DELETE" >&2
    fi
  else
    echo "NO_PROTECTED_SERVICE_SWITCH_ATTEMPTED" >&2
  fi
  exit "$code"
}
if [[ "${1:---check}" == --check && $# -le 1 ]]; then preflight; exit 0; fi
[[ "${1:-}" == --apply-founder-approved && $# -eq 1 ]] || die "exact_founder_approval_flag_required"
[[ "$EUID" == 0 ]] || die "root_owned_release_installer_required"
preflight
trap 'rollback_once "$?" "$STEP"' ERR
STEP=copy
if [[ ! -d "$NEW" ]]; then
  cp -a -- "$CAND" "$NEW"
  chown -R root:root "$NEW"
  chmod -R go-w "$NEW"
fi
verify_files "$NEW"
STEP=override
override_contents > "$DROP"
DROP_CREATED=1
chmod 0644 "$DROP"
STEP=restart
systemctl daemon-reload
systemctl restart "$UNIT"
STEP=readiness
ready=0
for attempt in $(seq 1 40); do
  if [[ "$(systemctl show "$UNIT" -p ActiveState --value)" == active && -S "$LEGACY" && -S "$IDENTITY" ]] &&
       legacy_canary && identity_denial_canary; then ready=1; break; fi
  sleep 0.5
done
[[ "$ready" == 1 && "$(systemctl show "$UNIT" -p WorkingDirectory --value)" == "$NEW" ]] || false
trap - ERR
echo "ROOT_HELPER_IDENTITY_READONLY_SOCKET_ACTIVATED; NO_KEYS_NO_TASKS"
