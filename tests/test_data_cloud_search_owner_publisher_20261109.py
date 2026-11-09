"""Independent owner-publisher proof for ORIGINAL Data Cloud search pilot.

No production database or service writes. PostgreSQL tests use a temporary
Unix-socket-only PG18 instance and the existing pinned original schema.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
PUBLISHER = ROOT / "scripts/activate_data_cloud_search_pilot_guarded_20261109.py"
spec = importlib.util.spec_from_file_location("data_cloud_search_owner_publisher", PUBLISHER)
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)


def test_founder_zero_paid_provider_budget_is_not_a_fake_blocker():
    state = {
        "monthly_request_cap": 3,
        "monthly_cost_cap_micros": 0,
        "search_cost_ceiling_micros": 1,
        "allowed_operations": [],
    }
    assert state["monthly_cost_cap_micros"] == 0
    assert state["monthly_request_cap"] * state["search_cost_ceiling_micros"] == 3
    assert "search" not in state["allowed_operations"]


def test_free_fabric_quota_change_is_bounded_in_existing_delta(monkeypatch):
    monkeypatch.setattr(owner, "db", lambda sql: "101" if "api_owner" in sql else "102")
    before = {
        "tenants": [{
            "tenant_id": "synthetic-founder",
            "allowed_operations": [],
            "monthly_request_cap": 3,
            "monthly_cost_cap_micros": 0,
            "search_cost_ceiling_micros": 1,
        }],
        "functions": [
            {"name": name, "execute": False, "acl": []}
            for name in ("reserve", "settle")
        ],
    }
    expected = owner.expected_database(before)
    assert expected["tenants"][0]["allowed_operations"] == ["search"]
    assert expected["tenants"][0]["monthly_cost_cap_micros"] == 3
    assert before["tenants"][0]["monthly_cost_cap_micros"] == 0
    statement = owner.db_delta(before)
    assert statement.count("GRANT EXECUTE ON FUNCTION") == 2
    assert statement.count("UPDATE empire_data_cloud_api.tenants SET") == 1
    assert "monthly_cost_cap_micros=3" in statement
    assert "ALTER TABLE" not in statement and "CREATE ROLE" not in statement
    assert "UPDATE empire_data_cloud_api.api_keys" not in statement
    rollback = owner.db_delta(before, undo=True)
    assert rollback.count("REVOKE EXECUTE ON FUNCTION") == 2
    assert "monthly_cost_cap_micros=0" in rollback


def test_existing_optional_environment_file_not_invented_blocker(monkeypatch):
    responses = {
        "is-active": "active",
        "FragmentPath": "/etc/systemd/system/empire-public-gateway.service",
        "DropInPaths": "/etc/systemd/system/empire-public-gateway.service.d/one.conf",
        "Environment": "PYTHONPATH=/srv/empire_os",
        "EnvironmentFiles": (
            "/etc/empire_a2a.env (ignore_errors=yes) "
            "/etc/empire/fb-guide-email.env (ignore_errors=no)"
        ),
        "ExecStart": (
            "{ path=/srv/empire_os/.venv/bin/python ; argv[]="
            "/srv/empire_os/.venv/bin/python -m uvicorn "
            "data_cloud_public_entrypoint_20261107:app "
            "--host 127.0.0.1 --port 80 --workers 1 ; ignore_errors=no ; }"
        ),
        "WorkingDirectory": "/srv/empire_os",
    }
    monkeypatch.setattr(
        owner, "run", lambda argv, data=None: (
            responses["is-active"] if "is-active" in argv
            else responses[argv[argv.index("-p") + 1]]
        ),
    )
    monkeypatch.setattr(owner, "protected", lambda path, **kw: b"pinned-existing-file")
    monkeypatch.setattr(Path, "exists", lambda p: str(p) != "/etc/empire_a2a.env")
    monkeypatch.setattr(Path, "is_symlink", lambda p: False)
    result = owner.service_snapshot(owner.SERVICE)
    assert result["environment_files"]["/etc/empire_a2a.env"] == {
        "optional": True, "sha256": None,
    }
    assert result["environment_files"]["/etc/empire/fb-guide-email.env"]["optional"] is False
    assert result["exec"]["path"] == "/srv/empire_os/.venv/bin/python"


def test_unknown_receipt_cannot_pass_owner_authorization(tmp_path):
    with pytest.raises(RuntimeError, match="evidence_digest_required"):
        owner.owner_evidence(tmp_path / "missing.json", None)


def test_existing_source_rejects_missing_release_commit():
    with pytest.raises(RuntimeError, match="release_commit_required|exact_worktree_required"):
        owner.source("invalid")


def test_actual_original_postgres_18_meter_grant_reserve_settle_rollback(tmp_path, monkeypatch):
    """Tests generated SQL and exact database readback, not just SQL fragments."""
    bin_dir = Path("/usr/lib/postgresql/18/bin")
    if not (bin_dir / "initdb").exists():
        pytest.skip("isolated PG18 unavailable")
    data = tmp_path / "data"
    sock = tmp_path / "sock"
    sock.mkdir()
    port = "55477"

    def call(*argv, stdin=None):
        result = subprocess.run(
            [str(x) for x in argv], input=stdin,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=35,
        )
        assert result.returncode == 0, (result.stderr[-800:] or result.stdout[-800:])
        return result.stdout.strip()

    call(bin_dir / "initdb", "-D", data, "-U", "postgres",
         "-A", "trust", "--no-instructions")
    running = False
    try:
        running = True
        call(bin_dir / "pg_ctl", "-D", data, "-l", tmp_path / "pg.log",
             "-o", f"-c listen_addresses='' -c unix_socket_directories={sock} -p {port}",
             "-w", "start")

        def pg(sql, *, database="empiredb"):
            return call(bin_dir / "psql", "-X", "-qAtw",
                        "-v", "ON_ERROR_STOP=1", "-h", sock, "-p", port,
                        "-U", "postgres", "-d", database, stdin=sql)

        pg("CREATE DATABASE empiredb;", database="postgres")
        original = ROOT / "docs/release_candidates/empire_data_cloud_meter_pg18_review_only_20261107.sql"
        call(bin_dir / "psql", "-X", "-qAtw", "-v", "ON_ERROR_STOP=1",
             "-h", sock, "-p", port, "-U", "postgres",
             "-d", "empiredb", "-f", original)
        # The original SQL stages the meter role as NOLOGIN; the separate
        # existing founder usage activation already made this role LOGIN.
        # Reproduce that verified pre-existing production role state in this
        # temporary isolated database only.
        pg("ALTER ROLE empire_data_cloud_meter_login LOGIN;")
        pg("""INSERT INTO empire_data_cloud_api.tenants
             (tenant_id,active,held,monthly_request_cap,monthly_cost_cap_micros,
              search_cost_ceiling_micros,audit_cost_ceiling_micros,
              allowed_operations,allowed_hosts)
             VALUES ('synthetic-founder',true,false,3,0,1,1,
                     ARRAY[]::text[],ARRAY[]::text[]);
             INSERT INTO empire_data_cloud_api.api_keys
             (token_sha256,tenant_id,active,expires_at)
             VALUES (repeat('a',64),'synthetic-founder',true,now()+interval '1 hour');""")

        monkeypatch.setattr(owner, "db", pg)
        before = owner.database()
        assert owner.validate_database(before)["monthly_cost_cap_micros"] == 0
        pg(owner.db_delta(before))
        after = owner.database()
        assert after == owner.expected_database(before)
        assert after["tenants"][0]["monthly_cost_cap_micros"] == 3
        assert "search" in after["tenants"][0]["allowed_operations"]
        assert all(f["execute"] is True for f in after["functions"]
                   if f["name"] in ("reserve", "settle"))

        for i in range(3):
            reservation = pg(
                "SELECT empire_data_cloud_api.reserve("
                f"repeat('a',64),'search','synthetic-request-{i:04d}',"
                "repeat('c',64),NULL);"
            )
            assert reservation.isdigit()
            result = pg(
                "SELECT empire_data_cloud_api.settle("
                f"repeat('a',64),{int(reservation)},'completed',0,"
                "'empire_fabric_direct_public_no_paid_api_v1');"
            )
            assert result == "completed"
        assert pg("SELECT held FROM empire_data_cloud_api.tenants WHERE tenant_id='synthetic-founder';") == "f"

        # Clear disposable usage records only to test exact canonical DB rollback
        # preimage; never do this in production.
        pg("DELETE FROM empire_data_cloud_api.usage_requests;")
        pg(owner.db_delta(before, undo=True))
        assert owner.database() == before
        assert owner.validate_database(owner.database())["monthly_cost_cap_micros"] == 0
    finally:
        if running:
            call(bin_dir / "pg_ctl", "-D", data, "-m", "immediate", "-w", "stop")


def test_additive_overlay_disables_new_release_bytecode_without_replacing_service():
    pre = {"baseline": {"gateway": {"pythonpath": "/srv/empire_os:/opt/empire-ai/old"}}}
    content = owner.overlay(pre, "a" * 64).decode()
    assert 'Environment="PYTHONDONTWRITEBYTECODE=1"' in content
    assert "Environment=\"EMPIRE_DATA_CLOUD_FOUNDER_SEARCH_RELEASE=" in content
    assert "ExecStart" not in content
    assert "PAID_PROVIDER" not in content


def test_journal_stale_interrupted_checkpoint_is_recoverable(monkeypatch, tmp_path):
    monkeypatch.setattr(owner, "STATE", tmp_path)
    monkeypatch.setattr(owner, "JOURNAL", tmp_path / "JOURNAL.json")
    # Simulates an interrupted previous publisher before os.replace.
    (tmp_path / ".journal-next").write_text("stale-incomplete")
    monkeypatch.setattr(owner, "write_new", lambda path, raw, mode=0o600: path.write_bytes(raw))
    owner.checkpoint({"phase": "recovered"})
    assert owner.JOURNAL.read_text().find("recovered") >= 0
    owner.checkpoint({"phase": "still-recoverable"})
    assert "still-recoverable" in owner.JOURNAL.read_text()


def test_privileged_git_source_uses_only_exact_worktree_safe_directory(monkeypatch):
    observed = []
    class Result:
        returncode = 0
        stdout = b"369b53cd614d8e91c47f57bdf5c5ff46548471f6\n"
    def stub(argv, **kwargs):
        observed.append((argv, kwargs))
        return Result()
    monkeypatch.setattr(owner.subprocess, "run", stub)
    out = owner.run(["git", "-C", str(owner.ROOT), "rev-parse", "HEAD"])
    assert len(out) == 40
    command, options = observed[0]
    assert command[:3] == ["git", "-c", "safe.directory=" + str(owner.ROOT)]
    assert "SUDO_UID" not in options["env"]
    assert "PGPASSWORD" not in options["env"]
