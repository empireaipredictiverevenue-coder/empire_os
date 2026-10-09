"""One-time CRM reader role bootstrap on a disposable PostgreSQL 18 cluster.

Exercises the exact migration bootstrap SQL; no production DB connections.
"""
from pathlib import Path
import socket
import subprocess
import tempfile

import pytest

BIN = Path("/usr/lib/postgresql/18/bin")
SQL_FILE = (
    Path(__file__).resolve().parents[1]
    / "migrations/empiredb/040_revenue_crm_tenant_reader_views.sql"
)


def test_040_role_bootstrap_requires_privileged_dba_and_no_login_grant():
    if not (BIN / "pg_ctl").exists():
        pytest.skip("PostgreSQL 18 unavailable")
    original = SQL_FILE.read_text()
    bootstrap = original.split("SET LOCAL ROLE empiredb_migrator;", 1)[0] + "\nCOMMIT;\n"
    assert "CREATE ROLE empire_revenue_crm_reader NOLOGIN NOINHERIT" in bootstrap
    assert "GRANT empire_revenue_crm_reader TO" not in original
    assert "ALTER TABLE public.tenant_business_entity_bindings" not in original
    with tempfile.TemporaryDirectory(prefix="empire-crm-role-", dir="/tmp") as temp:
        root = Path(temp)
        data = root / "db"
        sock = root / "socket"
        sock.mkdir(mode=0o700)
        init = subprocess.run(
            [str(BIN / "initdb"), "-D", str(data), "-A", "trust",
             "--no-locale", "-E", "UTF8"],
            capture_output=True, text=True, timeout=20,
        )
        assert init.returncode == 0, init.stderr
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        started = subprocess.run(
            [str(BIN / "pg_ctl"), "-D", str(data),
             "-l", str(root / "fixture-only.log"),
             "-o", f"-c listen_addresses='' -k {sock} -p {port}",
             "-w", "start"],
            capture_output=True, text=True, timeout=20,
        )
        assert started.returncode == 0, started.stderr

        def run(query, *, user="ubuntu", expected=0):
            result = subprocess.run(
                [str(BIN / "psql"), "-X", "-At", "-v", "ON_ERROR_STOP=1",
                 "-h", str(sock), "-p", str(port), "-U", user,
                 "-d", "crm_release_fixture", "-c", query],
                capture_output=True, text=True, timeout=15,
            )
            assert (result.returncode == 0) == (expected == 0), (
                result.stdout, result.stderr[:400],
            )
            return result.stdout.strip()
        try:
            create = subprocess.run(
                [str(BIN / "psql"), "-X", "-At", "-v", "ON_ERROR_STOP=1",
                 "-h", str(sock), "-p", str(port), "-U", "ubuntu",
                 "-d", "postgres", "-c", "CREATE DATABASE crm_release_fixture;"],
                capture_output=True, text=True, timeout=10,
            )
            assert create.returncode == 0, create.stderr
            run("CREATE ROLE empiredb_migrator NOLOGIN; "
                "CREATE ROLE crm_nonpriv LOGIN NOINHERIT; "
                "GRANT CONNECT ON DATABASE crm_release_fixture TO crm_nonpriv;")
            assert run("SELECT count(*) FROM pg_roles "
                       "WHERE rolname='empire_revenue_crm_reader'") == "0"
            run(bootstrap, user="crm_nonpriv", expected=1)
            assert run("SELECT count(*) FROM pg_roles "
                       "WHERE rolname='empire_revenue_crm_reader'") == "0"
            run(bootstrap)
            result = run(
                "SELECT rolcanlogin,rolinherit,rolsuper,rolbypassrls,rolcreaterole "
                "FROM pg_roles WHERE rolname='empire_revenue_crm_reader'"
            )
            assert result == "f|f|f|f|f"
            assert run(
                "SELECT pg_has_role('crm_nonpriv','empire_revenue_crm_reader','MEMBER')"
            ) == "f"
            # If already provisioned, the bootstrap does not grant access.
            run(bootstrap)
            assert run(
                "SELECT pg_has_role('crm_nonpriv','empire_revenue_crm_reader','MEMBER')"
            ) == "f"
        finally:
            subprocess.run(
                [str(BIN / "pg_ctl"), "-D", str(data), "-m", "immediate",
                 "-w", "stop"],
                capture_output=True, text=True, timeout=20,
            )
