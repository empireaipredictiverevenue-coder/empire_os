"""Guarded Cloud v2 upgrade is exact-source and timer/rollback bounded."""
from pathlib import Path
import subprocess
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / (
    "scripts/upgrade_guarded_predictive_cloud_framework_20261021.sh"
)


@pytest.mark.parametrize("args", [
    (), ("--check",), ("--check", "main"),
    ("--apply-owner-approved-observe", "bogus"),
    ("--wrong", "0" * 40),
])
def test_no_implicit_upgrade_or_bad_commit(args):
    result = subprocess.run(
        ["bash", str(SCRIPT), *args], text=True, capture_output=True,
        timeout=12, check=False,
    )
    assert result.returncode != 0
    assert "CLOUD_FRAMEWORK_UPGRADE_DEPLOYED" not in result.stdout


def test_guard_exact_old_hash_and_restore_service():
    code = SCRIPT.read_text()
    for required in (
        "BEFORE_UNIT_SHA=", "BEFORE_DROPIN_SHA=",
        "BEFORE_OLD_WRITER_SHA=", "BEFORE_OLD_RUNNER_SHA=",
        "SOURCE_COMMIT=$SHA", "sha256sum --status -c",
        "archive \"$SHA\"", 'chown -R root:root "$stage"',
        'systemctl stop "$TIMER"', 'systemctl start "$TIMER"',
        'cp -p -- "$backup/previous_dropin.conf" "$DROPIN"',
        "systemctl daemon-reload", "flock -n 9",
        "read_predictive_cloud_status", "CLOUD_FRAMEWORK_STATUS_AND_OPTIMIZATION_REFRESH_VERIFIED",
        "third_party_services", "framework_operational",
        "optimization_fabric_latest.json",
        "PAYMENTS_OUTBOUND_UNCHANGED",
    ):
        assert required in code
    assert code.rfind('systemctl start "$TIMER"') < code.rfind("rollback_needed=0")
    for forbidden in ("CREATE ROLE", "GRANT SELECT", "ALTER TABLE", "DROP TABLE", "curl "):
        assert forbidden not in code


def test_after_rollback_reuses_only_verified_root_owned_release():
    code = SCRIPT.read_text()
    assert 'if [[ -e "$TARGET" ]]; then' in code
    assert '[[ "$(stat -c \'%u\' "$TARGET")" == 0 ]]' in code
    assert 'find "$TARGET" ! -user root -print -quit' in code
    assert 'find "$TARGET" -perm /022 -print -quit' in code
    assert 'find "$TARGET" -type l -print -quit' in code
    assert '(cd "$TARGET" && sha256sum --status -c "$MANIFEST")' in code
    assert "PREVIOUS_VERIFIED_ROOT_OWNED_RELEASE_REUSED" in code
    assert code.index("rollback_needed=1") > code.index(
        'if [[ ! -e "$TARGET" ]]; then'
    )


def test_in_process_verifier_uses_pinned_api_not_cwd_shadow():
    code = SCRIPT.read_text()
    assert 'env -i PATH=/usr/bin:/bin PYTHONPATH="$TARGET"' in code
    assert '/srv/empire_os/.venv/bin/python -P -B -' in code
    assert 'EMPIRE_CLOUD_EXPECTED_CODE="$TARGET"' in code
    assert 'from empire_os import predictive_cloud_status_api as status_api' in code
    assert 'Path(status_api.__file__).resolve() == expected.resolve()' in code
    assert '"WRONG_CLOUD_API_MODULE_HOLD"' in code
    assert 'status=read_predictive_cloud_status(root/"status_latest.json", now=now)' in code


def test_existing_cloud_timer_and_other_services_never_replaced():
    code = SCRIPT.read_text()
    assert "predictive_cloud_guard_f4fe409c56fa" in code
    assert 'SERVICE=\'empire-predictive-cloud-materializer.service\'' in code
    assert 'TIMER=\'empire-predictive-cloud-materializer.timer\'' in code
    assert "/srv/empire_os/runtime/predictive_cloud" in code
    assert "founder-dashboard-api" not in code
    assert "empire-predictive-intelligence.service" not in code
