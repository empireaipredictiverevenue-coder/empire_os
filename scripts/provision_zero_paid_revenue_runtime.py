#!/usr/bin/env python3
"""Root-only least-privilege runtime credential provisioner."""
from __future__ import annotations

import base64
import json
import os
import secrets
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ENV_FILE = Path("/etc/empire_a2a.env")
KEY_FILE = Path("/etc/empire_a2a_agent_ed25519.pem")
ROLES = (
    ("empire_owned_campaign_runtime", "empire_owned_campaign_ingest"),
    ("empire_a2a_identity_runtime", "empire_a2a_identity_nonce_writer"),
    ("empire_a2a_intent_runtime", "empire_a2a_intent_writer"),
)

def _quote(value: str) -> str:
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"') + '"'


def _runtime_dsn(base: dict, login: str, password: str) -> str:
    clean = dict(base)
    for key in ("user", "password", "application_name", "options"):
        clean.pop(key, None)
    return make_conninfo(
        **clean,
        user=login,
        password=password,
        application_name=login,
        connect_timeout="5",
    )


def _ensure_roles(base_dsn: str) -> dict[str, str]:
    passwords = {login: secrets.token_urlsafe(36) for login, _ in ROLES}
    with psycopg.connect(base_dsn, autocommit=True) as conn:
        for login, capability in ROLES:
            exists = conn.execute(
                "SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname=%s)",
                (login,),
            ).fetchone()[0]
            if not exists:
                conn.execute(sql.SQL(
                    "CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE"
                ).format(sql.Identifier(login)))
            conn.execute(sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                sql.Identifier(login), sql.Literal(passwords[login])
            ))
            conn.execute(sql.SQL(
                "ALTER ROLE {} SET statement_timeout = '3s'"
            ).format(sql.Identifier(login)))
            conn.execute(sql.SQL("REVOKE ALL ON SCHEMA public FROM {}").format(
                sql.Identifier(login)
            ))
            conn.execute(sql.SQL("GRANT {} TO {}").format(
                sql.Identifier(capability), sql.Identifier(login)
            ))
    return passwords


def _verify_roles(base_dsn: str, passwords: dict[str, str]) -> None:
    base = conninfo_to_dict(base_dsn)
    checks = (
        ("empire_owned_campaign_runtime", "empire_owned_campaign_ingest", "public.record_owned_campaign_enquiry(jsonb)"),
        ("empire_a2a_identity_runtime", "empire_a2a_identity_nonce_writer", "public.consume_a2a_identity_nonce(text,text,text,timestamptz)"),
        ("empire_a2a_intent_runtime", "empire_a2a_intent_writer", "public.record_a2a_commercial_intent(text,text,text,timestamptz,text,text,jsonb,jsonb)"),
    )
    for login, role, function in checks:
        dsn = _runtime_dsn(base, login, passwords[login])
        with psycopg.connect(dsn) as conn:
            conn.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
            current = conn.execute("SELECT current_user").fetchone()[0]
            allowed = conn.execute(
                "SELECT has_function_privilege(current_user,%s,'EXECUTE')", (function,)
            ).fetchone()[0]
            if current != role or allowed is not True:
                raise RuntimeError(f"runtime role verification failed: {login}")


def _load_or_create_key() -> tuple[Ed25519PrivateKey, str]:
    if KEY_FILE.exists():
        private = serialization.load_pem_private_key(KEY_FILE.read_bytes(), password=None)
    else:
        private = Ed25519PrivateKey.generate()
        KEY_FILE.write_bytes(private.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ))
        os.chmod(KEY_FILE, 0o600)
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return private, base64.b64encode(public).decode("ascii")


def _write_env(base_dsn: str, passwords: dict[str, str], public_key: str) -> None:
    base = conninfo_to_dict(base_dsn)
    trusted = json.dumps(
        {"empire-astra-v1": public_key}, separators=(",", ":")
    )
    lines = [
        "EMPIRE_DATA_BACKEND=empiredb",
        "EMPIRE_OWNED_CAMPAIGN_DSN=" + _quote(_runtime_dsn(
            base, "empire_owned_campaign_runtime", passwords["empire_owned_campaign_runtime"]
        )),
        "EMPIRE_A2A_TRUSTED_ED25519_KEYS_JSON=" + _quote(trusted),
        "EMPIRE_A2A_IDENTITY_DSN=" + _quote(_runtime_dsn(
            base, "empire_a2a_identity_runtime", passwords["empire_a2a_identity_runtime"]
        )),
        "EMPIRE_A2A_INTENT_DSN=" + _quote(_runtime_dsn(
            base, "empire_a2a_intent_runtime", passwords["empire_a2a_intent_runtime"]
        )),
        "EMPIRE_A2A_LIVE_VERIFIED=false",
    ]
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(ENV_FILE, 0o600)


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("run as root")
    base_dsn = str(os.environ.get("EMPIREDB_MIGRATOR_DSN") or "").strip()
    if not base_dsn:
        raise SystemExit("EMPIREDB_MIGRATOR_DSN required")
    passwords = _ensure_roles(base_dsn)
    _verify_roles(base_dsn, passwords)
    _, public_key = _load_or_create_key()
    _write_env(base_dsn, passwords, public_key)
    print(json.dumps({
        "status": "ready",
        "env_file": str(ENV_FILE),
        "key_id": "empire-astra-v1",
        "roles": [login for login, _ in ROLES],
        "secrets_printed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
