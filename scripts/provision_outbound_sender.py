#!/usr/bin/env python3
"""Provision the dedicated Phase 3E outbound sender credential.

Dry-run by default. Production mutation requires BOTH --apply and
--ack-production. Secrets are never printed.
"""
from __future__ import annotations

import argparse
import os
import secrets
from pathlib import Path
from urllib.parse import quote

ROLE = "empire_outbound_sender_login"
ENV_KEY = "EMPIRE_OUTBOUND_SENDER_DSN"
DEFAULT_ENV = Path("/srv/empire_os/.env")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--ack-production", action="store_true")
    p.add_argument("--env-file", type=Path, default=DEFAULT_ENV)
    return p


def build_dsn(base_dsn: str, password: str) -> str:
    from urllib.parse import urlsplit, urlunsplit
    parts = urlsplit(base_dsn)
    if not parts.hostname or not parts.scheme.startswith("postgres"):
        raise ValueError("valid PostgreSQL admin DSN required")
    host = parts.hostname
    port = f":{parts.port}" if parts.port else ""
    db = parts.path or "/postgres"
    userinfo = f"{ROLE}:{quote(password, safe='')}"
    return urlunsplit((parts.scheme, f"{userinfo}@{host}{port}", db, parts.query, ""))


def replace_env(path: Path, value: str) -> None:
    existing = path.read_text() if path.exists() else ""
    lines = [line for line in existing.splitlines() if not line.startswith(ENV_KEY + "=")]
    lines.append(f"{ENV_KEY}={value}")
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("\n".join(lines) + "\n")
    os.chmod(tmp, 0o600)
    tmp.replace(path)


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    if args.apply != args.ack_production:
        raise SystemExit("production provisioning requires --apply --ack-production together")
    if not args.apply:
        print("dry-run: sender credential would be generated and installed; no mutation performed")
        return 0
    admin_dsn = os.getenv("EMPIRE_DB_ADMIN_DSN", "").strip()
    if not admin_dsn:
        raise SystemExit("EMPIRE_DB_ADMIN_DSN is required for production provisioning")
    password = secrets.token_urlsafe(36)
    import psycopg
    with psycopg.connect(admin_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("alter role empire_outbound_sender_login password %s", (password,))
    replace_env(args.env_file, build_dsn(admin_dsn, password))
    print("sender credential provisioned; secret not displayed")
    return 0
