"""No-root tests for reusing the original root-protected founder reader."""
from __future__ import annotations

from pathlib import Path
import os
import subprocess

BRIDGE = Path(__file__).resolve().parents[1] / (
    "scripts/run_predictive_existing_founder_tenant_reader_20261021.sh"
)


def _run(*args, env=None):
    return subprocess.run(
        ["/bin/bash", str(BRIDGE), *args],
        env=env, capture_output=True, text=True,
        timeout=20, check=False,
    )


def test_check_mode_only_verifies_pinned_release():
    result = _run("--check")
    assert result.returncode == 0
    assert "PINNED_PREDICTIVE_RELEASE_VERIFIED" in result.stdout
    assert "ROOT_OWNED_CREDENTIAL_NOT_TESTED_IN_CHECK_MODE" in result.stdout
    assert "password" not in result.stdout.casefold()


def test_invalid_mode_refuses_privileged_execution():
    result = _run("give-me-root")
    assert result.returncode == 2
    assert "Usage:" in result.stderr


def test_root_invocations_are_fixed_and_never_embed_password(tmp_path):
    # Fake sudo resides in a test-only directory. It merely records argv.
    fake = tmp_path / "sudo"
    logfile = tmp_path / "calls"
    fake.write_text(
        "#!/bin/sh\n"
        "printf '%s\\n' 'CALL_START' >> \"$BRIDGE_TEST_CALLS\"\n"
        "printf '%s\\n' \"$@\" >> \"$BRIDGE_TEST_CALLS\"\n"
        "printf '%s\\n' '{\"status\":\"MOCK_NO_DATABASE_USED\"}'\n"
    )
    fake.chmod(0o700)
    env = dict(os.environ)
    env.update(
        PATH=str(tmp_path) + ":" + os.environ.get("PATH", "/usr/bin:/bin"),
        BRIDGE_TEST_CALLS=str(logfile),
    )
    result = _run("both", env=env)
    assert result.returncode == 0, result.stderr
    assert result.stdout.count("MOCK_NO_DATABASE_USED") == 2
    calls = logfile.read_text()
    assert calls.count("CALL_START") == 2
    assert calls.count("scripts.review_predictive_tenant_outcome_reader_preflight_20261020") == 1
    assert calls.count("scripts.review_predictive_tenant_terminal_cohort_20261020") == 1
    assert calls.count("PGPASSFILE=/etc/empire/verified-order-reader/reader.pgpass") == 2
    assert calls.count("user=empire_verified_order_tenant_login") == 2
    assert "user=postgres" not in calls
    assert "password=" not in calls.lower()
    assert "EMPIREDB_DSN=" not in calls
    assert result.stdout.count("password") == 0


def test_existing_observe_tenant_commands_delegate_without_live_db(tmp_path):
    launcher = Path("/home/ubuntu/.local/bin/empire-predictive-observe")
    if not launcher.is_file():
        import pytest
        pytest.skip("owner OBSERVE launcher not installed on this test host")
    fake = tmp_path / "sudo"
    calls = tmp_path / "calls"
    fake.write_text(
        "#!/bin/sh\n"
        "printf '%s\\n' \"$@\" >> \"$BRIDGE_TEST_CALLS\"\n"
        "printf '%s\\n' '{\"status\":\"MOCK_READ_ONLY\"}'\n"
    )
    fake.chmod(0o700)
    env = dict(os.environ)
    env.update(
        PATH=str(tmp_path) + ":" + os.environ.get("PATH", "/usr/bin:/bin"),
        BRIDGE_TEST_CALLS=str(calls),
    )
    for command in ("tenant-evidence", "tenant-cohort"):
        result = subprocess.run(
            [str(launcher), command], capture_output=True, text=True,
            env=env, timeout=20, check=False,
        )
        assert result.returncode == 0, result.stderr
        assert "MOCK_READ_ONLY" in result.stdout
    instructions = calls.read_text()
    assert instructions.count("scripts.review_predictive_tenant_outcome_reader_preflight_20261020") == 1
    assert instructions.count("scripts.review_predictive_tenant_terminal_cohort_20261020") == 1
    assert "password=" not in instructions.lower()
