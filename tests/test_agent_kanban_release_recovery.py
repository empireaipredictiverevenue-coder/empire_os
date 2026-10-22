"""Mock-only proof of guarded deployment retries and single rollback.

Do not invoke live services, systemd changes, CRM credentials or root.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts/deploy_pinned_agent_kanban_crm_20261022.sh"
)


def _function(source: str, start: str, following: str) -> str:
    return start + source.split(start, 1)[1].split(following, 1)[0]


def test_script_is_valid_bash():
    completed = subprocess.run(
        ["bash", "-n", str(SCRIPT)],
        capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_startup_waits_through_transient_http_000_before_401(tmp_path):
    source = SCRIPT.read_text()
    fn = _function(source, "ready() {", "\nvalidate_release_inventory() {")
    count = tmp_path / "probe_count"
    count.write_text("0")
    script = (
        'set -euo pipefail\n'
        'UNIT=synthetic.service\n'
        f'COUNT="{count}"\n'
        'systemctl() { echo active; }\n'
        'sleep() { :; }\n'
        'code() {\n'
        '  if [[ "$1" == "/health" ]]; then echo 200; return; fi\n'
        '  local num\n'
        '  num=$(cat "$COUNT")\n'
        '  num=$((num + 1))\n'
        '  echo "$num" > "$COUNT"\n'
        '  if (( num < 4 )); then echo 000; else echo 401; fi\n'
        '}\n'
        + fn
        + '\nready 401\n'
        + 'echo WAIT_SUCCEEDED\n'
    )
    done = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert "WAIT_SUCCEEDED" in done.stdout
    assert int(count.read_text()) >= 4


def test_health_can_be_ready_but_wrong_route_denied(tmp_path):
    source = SCRIPT.read_text()
    fn = _function(source, "ready() {", "\nvalidate_release_inventory() {")
    script = (
        'set -euo pipefail\nUNIT=synthetic.service\n'
        'systemctl() { echo active; }\n'
        'sleep() { :; }\n'
        'code() { if [[ "$1" == "/health" ]]; then echo 200; else echo 404; fi; }\n'
        + fn
        + '\nready 401\n'
    )
    done = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert done.returncode == 1
    assert "RELEASE_HTTP_NOT_READY expected=401" in done.stderr


def test_failed_before_switch_never_claims_rollback():
    source = SCRIPT.read_text()
    fn = _function(source, "rollback_on_error() {", '\nif [[ "${1:---check}"')
    script = (
        'set -euo pipefail\n'
        'DROP_CREATED=0\n'
        'DROP="/nonexistent/should_not_be_touched"\n'
        + fn + '\nrollback_on_error 17 86 restart\n'
    )
    done = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert done.returncode == 17
    assert done.stderr.count("DEPLOYMENT_FAILED") == 1
    assert done.stderr.count("RELEASE_SWITCH_NOT_APPLIED") == 1
    assert "ROLLED_BACK_TO_PRIOR" not in done.stderr


def test_preflight_allows_exact_existing_protected_stage_but_fails_closed():
    source = SCRIPT.read_text()
    assert "EXISTING_PROTECTED_STAGE_VERIFIED" in source
    assert "previously_staged_release_changed_or_incomplete" in source
    assert "staged_release_not_root_owned_immutable" in source
    assert "existing_release_override_needs_owner_review" in source
    assert "test ! -e \"$NEW\" &&" not in source
    assert "trap - ERR" in source


def test_one_rollback_removes_only_own_exact_override(tmp_path):
    source = SCRIPT.read_text()
    fn = _function(source, "rollback_on_error() {", '\nif [[ "${1:---check}"')
    drop = tmp_path / "dedicated-release.conf"
    stage = str(tmp_path / "pinned-release")
    drop.write_text(
        "[Service]\n"
        f"WorkingDirectory={stage}\n"
        f"Environment=PYTHONPATH={stage}\n"
    )
    script = (
        'set -euo pipefail\n'
        'DROP_CREATED=1\n'
        f'DROP="{drop}"\n'
        f'NEW="{stage}"\n'
        'UNIT=synthetic.service\n'
        'systemctl() { :; }\n'
        'ready() { [[ "$1" == 404 ]]; }\n'
        + fn + '\nrollback_on_error 19 89 http_readiness\n'
    )
    done = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert done.returncode == 19
    assert "ROLLED_BACK_TO_PRIOR_PINNED_RELEASE" in done.stderr
    assert done.stderr.count("ROLLED_BACK_TO_PRIOR_PINNED_RELEASE") == 1
    assert not drop.exists()


def test_changed_override_is_not_deleted_by_rollback(tmp_path):
    source = SCRIPT.read_text()
    fn = _function(source, "rollback_on_error() {", '\nif [[ "${1:---check}"')
    drop = tmp_path / "owned-by-another-release.conf"
    drop.write_text("[Service]\nWorkingDirectory=/different-release\n")
    script = (
        'set -euo pipefail\n'
        'DROP_CREATED=1\n'
        f'DROP="{drop}"\n'
        f'NEW="{tmp_path / "candidate"}"\n'
        'UNIT=synthetic.service\n'
        'systemctl() { exit 99; }\n'
        + fn + '\nrollback_on_error 23 89 http_readiness\n'
    )
    done = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert done.returncode == 23
    assert "NO_UNSAFE_AUTOMATIC_RESTORE" in done.stderr
    assert drop.exists()
