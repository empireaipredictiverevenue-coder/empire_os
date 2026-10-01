#!/usr/bin/env python3
"""Explicit root-only EmpireDB bootstrap; credentials never enter stdout/argv."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
from urllib.parse import quote

from empire_os.runtime_env import load_runtime_env

KEY = "EMPIRE_INTELLIGENCE_MATERIALIZER_DSN"
LOGIN = "empire_intelligence_materializer_login"
CONTRACT = Path(__file__).resolve().parents[1] / "deploy/empiredb/intelligence_materializer.sql"


def env_text(existing: str, dsn: str) -> str:
    if any(line.strip().removeprefix("export ").startswith(KEY + "=")
           for line in existing.splitlines()):
        raise ValueError("dedicated key already exists; explicit credential rotation required")
    return existing.rstrip("\n") + "\n" + KEY + "=" + dsn + "\n"


def provision(env_file: Path) -> None:
    if os.geteuid() != 0:
        raise ValueError("protected EmpireDB bootstrap requires root")
    if env_file.is_symlink():
        raise ValueError("environment file must not be a symlink")
    existing = env_file.read_text(encoding="utf-8")
    from psycopg.conninfo import conninfo_to_dict
    canonical = load_runtime_env("/etc/empiredb.env")
    if not canonical.get("EMPIREDB_DSN"):
        canonical = load_runtime_env("/etc/empire_os.env")
    base = conninfo_to_dict(canonical.get("EMPIREDB_DSN", ""))
    if base.get("dbname") != "empiredb" or base.get("host") not in {
        "127.0.0.1", "localhost", "::1", "/var/run/postgresql",
    }:
        raise ValueError("canonical local EmpireDB endpoint required")
    port = int(base.get("port", "5432"))
    password = secrets.token_urlsafe(36)
    dsn = f"postgresql://{LOGIN}:{quote(password, safe='')}@127.0.0.1:{port}/empiredb"
    content = env_text(existing, dsn)
    from psycopg import sql
    # SQL and credential are carried only on stdin, never process arguments.
    statement = "BEGIN;\n" + CONTRACT.read_text(encoding="utf-8")
    statement += sql.SQL("\nALTER ROLE {} PASSWORD {};\n").format(
        sql.Identifier(LOGIN), sql.Literal(password),
    ).as_string()
    statement += "COMMIT;\n"
    fd, temporary = tempfile.mkstemp(prefix=".intelligence-env-", dir=env_file.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            os.fchmod(handle.fileno(), 0o600)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        result = subprocess.run(
            ["runuser", "-u", "postgres", "--", "psql", "-X", "-q",
             "-v", "ON_ERROR_STOP=1", "-p", str(port), "-d", "empiredb"],
            input=statement, capture_output=True, text=True, timeout=60, check=False,
        )
        if result.returncode:
            raise ValueError("EmpireDB role bootstrap failed; transaction rolled back")
        os.replace(temporary, env_file)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--env-file", type=Path, default=Path("/etc/empire_os.env"))
    args = parser.parse_args()
    if not args.apply:
        print("prepared: dedicated EmpireDB role and protected runtime environment; no changes")
        return 0
    try:
        provision(args.env_file)
    except Exception:
        # Database and filesystem exceptions may contain SQL/credentials.
        print("blocked: dedicated materializer provisioning failed; secret details suppressed")
        return 1
    print("dedicated materializer provisioned; credential not displayed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
