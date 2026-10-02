#!/usr/bin/env python3
"""Provision the dedicated read-only Revenue Exchange runtime identity.

This is a founder-gated authority activation. Without --apply this script only
reports the intended action. Credentials are never printed or passed in argv.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from empire_os.runtime_env import load_runtime_env

KEY = "EMPIRE_REVENUE_EXCHANGE_READER_DSN"
LOGIN = "empire_revenue_exchange_reader_login"
CAPABILITY = "empire_revenue_exchange_reader"
ENV_FILE = Path("/etc/empire_revenue_exchange.env")


def _quote_env(value: str) -> str:
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"') + '"'


def _runtime_dsn(base_dsn: str, password: str) -> str:
    base = conninfo_to_dict(base_dsn)
    if base.get("dbname") != "empiredb":
        raise ValueError("canonical EmpireDB database required")
    host = str(base.get("host") or "").strip()
    if host not in {"127.0.0.1", "localhost", "::1", "/var/run/postgresql"}:
        raise ValueError("canonical local EmpireDB endpoint required")
    clean = dict(base)
    for key in ("user", "password", "application_name", "options"):
        clean.pop(key, None)
    return make_conninfo(
        **clean,
        user=LOGIN,
        password=password,
        application_name=LOGIN,
        connect_timeout="5",
    )


def _provision_sql(password: str) -> str:
    if not password.replace("-", "").replace("_", "").isalnum():
        raise ValueError("generated password contains unsafe characters")
    return f"""BEGIN;
DO $$
DECLARE extra_memberships integer;
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='{LOGIN}') THEN
    SELECT count(*) INTO extra_memberships
    FROM pg_auth_members m
    JOIN pg_roles member ON member.oid=m.member
    JOIN pg_roles granted ON granted.oid=m.roleid
    WHERE member.rolname='{LOGIN}'
      AND granted.rolname<>'{CAPABILITY}';
    IF extra_memberships > 0 THEN
      RAISE EXCEPTION 'dedicated login has unexpected role memberships';
    END IF;
  ELSE
    CREATE ROLE {LOGIN} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE;
  END IF;
END $$;
ALTER ROLE {LOGIN} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS PASSWORD '{password}';
ALTER ROLE {LOGIN} SET statement_timeout='5s';
GRANT CONNECT ON DATABASE empiredb TO {LOGIN};
REVOKE ALL ON SCHEMA public FROM {LOGIN};
GRANT {CAPABILITY} TO {LOGIN};
COMMIT;
"""


def _write_env_file(env_file: Path, dsn: str) -> None:
    if env_file.is_symlink():
        raise ValueError("environment file must not be a symlink")
    existing = ""
    if env_file.exists():
        existing = env_file.read_text(encoding="utf-8")
        if any(
            line.strip().removeprefix("export ").startswith(KEY + "=")
            for line in existing.splitlines()
        ):
            raise ValueError(
                "dedicated reader key already exists; explicit credential rotation required"
            )
    content = existing.rstrip("\n")
    if content:
        content += "\n"
    content += KEY + "=" + _quote_env(dsn) + "\n"
    env_file.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".revenue-exchange-reader-", dir=env_file.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            os.fchmod(handle.fileno(), 0o600)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, env_file)
        os.chmod(env_file, 0o600)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _apply_role(password: str) -> None:
    result = subprocess.run(
        [
            "runuser", "-u", "postgres", "--", "psql",
            "-X", "-q", "-v", "ON_ERROR_STOP=1", "-d", "empiredb",
        ],
        input=_provision_sql(password),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=60,
    )
    if result.returncode:
        raise ValueError("dedicated Revenue Exchange reader role provisioning failed")


def _verify_dedicated_reader(dsn: str) -> None:
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL ROLE " + CAPABILITY)
            role = cur.execute("SELECT current_user").fetchone()[0]
            select_ok = cur.execute(
                "SELECT has_table_privilege(current_user,%s,'SELECT')",
                ("public.revenue_exchange_observations",),
            ).fetchone()[0]
            write_flags = cur.execute(
                "SELECT has_table_privilege(current_user,%s,'INSERT'),"
                " has_table_privilege(current_user,%s,'UPDATE'),"
                " has_table_privilege(current_user,%s,'DELETE')",
                (
                    "public.revenue_exchange_observations",
                    "public.revenue_exchange_observations",
                    "public.revenue_exchange_observations",
                ),
            ).fetchone()
            cur.execute("SELECT 1 FROM public.revenue_exchange_observations LIMIT 1")
    if role != CAPABILITY or select_ok is not True or any(write_flags):
        raise ValueError("dedicated Revenue Exchange reader verification failed")


def provision(env_file: Path = ENV_FILE) -> dict[str, object]:
    if os.geteuid() != 0:
        raise ValueError("dedicated Revenue Exchange reader provisioning requires root")
    env = load_runtime_env("/etc/empiredb.env")
    base_dsn = str(env.get("EMPIREDB_DSN") or "").strip()
    if not base_dsn:
        raise ValueError("canonical EMPIREDB_DSN required")
    password = secrets.token_urlsafe(36)
    dsn = _runtime_dsn(base_dsn, password)
    _apply_role(password)
    _verify_dedicated_reader(dsn)
    _write_env_file(env_file, dsn)
    return {
        "status": "ready",
        "login": LOGIN,
        "capability": CAPABILITY,
        "env_file": str(env_file),
        "env_key": KEY,
        "read_only": True,
        "secrets_printed": False,
        "allocation_authority": "none",
        "pricing_authority": "none",
        "payment_authority": "none",
        "settlement_authority": "none",
        "revenue_recognition_authority": "none",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--env-file", type=Path, default=ENV_FILE)
    args = parser.parse_args()
    if not args.apply:
        print(json.dumps({
            "status": "prepared",
            "apply_required": True,
            "founder_gate": "authority_expansion",
            "login": LOGIN,
            "capability": CAPABILITY,
            "read_only": True,
            "changes_applied": False,
        }, sort_keys=True))
        return 0
    try:
        result = provision(args.env_file)
    except Exception:
        print(json.dumps({
            "status": "blocked",
            "reason": "dedicated_reader_provisioning_failed",
            "secrets_printed": False,
        }, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
