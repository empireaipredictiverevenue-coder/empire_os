#!/usr/bin/env python3
"""Run restricted Market GPS with a single systemd-supplied credential.

Root-owned credential file is never directly accessed by the unprivileged
worker. systemd LoadCredential copies its content into CREDENTIALS_DIRECTORY
with per-unit isolation. No process argv or stdout includes the DSN.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

KEY = "EMPIRE_INTELLIGENCE_MATERIALIZER_DSN"
FILENAME = "market-gps.dsn"
LOGIN = "empire_intelligence_materializer_login"

# Reuse the *existing* Market GPS systemd protected credential and write
# scope. This is a catalog-only, nonblocking probe; no TAM data is read.
TAM_PROBE_PATH = Path(
    "/srv/empire_os/runtime/market_sweeps/tam_reader_capability_latest.json"
)


def _real_protected_market_gps_execution(credential_directory: str | None) -> bool:
    """Only the genuine pre-existing systemd unit can attest a live DB probe."""
    if not credential_directory:
        return False
    path = Path(credential_directory)
    return (
        not path.is_symlink()
        and path == Path("/run/credentials/empire-market-gps.service")
        and bool(os.environ.get("INVOCATION_ID"))
    )


def _safe_probe_tam_catalog(dsn: str) -> dict[str, object]:
    from datetime import datetime, timezone
    try:
        from empire_os.tam_market_runtime import probe_tam_reader_capability
        result = probe_tam_reader_capability(dsn)
    except Exception:
        result = {
            "status": "RESTRICTED_CATALOG_PROBE_UNAVAILABLE",
            "migration_028_contract_verified": False,
            "no_data_rows_read": True,
            "execution_authority": "none",
        }
    # Whitelist fields: never persist SQL, credentials, connection strings or
    # exception details, even if a future probe accidentally returns them.
    boolean_fields = (
        "migration_028_contract_verified", "restricted_login_verified",
        "capability_role_verified", "function_exists",
        "security_definer_verified", "capability_execute_verified",
        "source_tables_present", "source_table_direct_read_grants",
    )
    allowed_status = {
        "PASS", "RESTRICTED_CATALOG_CONTRACT_INCOMPLETE",
        "RESTRICTED_CATALOG_PROBE_UNAVAILABLE",
        "INVALID_RESTRICTED_CATALOG_RESPONSE",
    }
    status = result.get("status")
    if not isinstance(status, str) or status not in allowed_status:
        status = "RESTRICTED_CATALOG_PROBE_UNAVAILABLE"
    proof = {
        "schema_version": "empire.tam_restricted_reader_capability_preflight.v1",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "source": "existing_market_gps_protected_systemd_credential",
        "mode": "OBSERVE",
        "status": status,
        "no_data_rows_read": True,
        "no_migration_applied": True,
        "no_credential_exported": True,
        "execution_authority": "none",
    }
    for key in boolean_fields:
        proof[key] = result.get(key) is True
    # A clean PASS must be backed by the complete restricted role/function/
    # grant contract, not just a string field claiming success.
    proof["migration_028_contract_verified"] = (
        status == "PASS"
        and all(proof[k] for k in (
            "restricted_login_verified", "capability_role_verified",
            "function_exists", "security_definer_verified",
            "capability_execute_verified", "source_tables_present",
        ))
        and not proof["source_table_direct_read_grants"]
    )
    return proof


def _persist_tam_probe(proof: dict[str, object]) -> None:
    # Owned file in the pre-existing service's ReadWritePaths only.
    import tempfile
    out = TAM_PROBE_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.is_symlink():
        raise ValueError("unsafe TAM preflight output")
    if not out.parent.is_dir():
        raise ValueError("invalid TAM preflight output directory")
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=out.parent,
        prefix=".tam-preflight-", suffix=".json", delete=False,
    ) as handle:
        temporary = Path(handle.name)
        try:
            os.chmod(temporary, 0o600)
            json.dump(proof, handle, indent=2, sort_keys=True)
            handle.write("\n")
        finally:
            pass
    try:
        temporary.replace(out)
        os.chmod(out, 0o600)
    finally:
        temporary.unlink(missing_ok=True)


def validated_credential(credential_directory: str | None) -> str:
    if not credential_directory:
        raise ValueError("systemd credential directory required")
    folder = Path(credential_directory)
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("invalid systemd credential directory")
    path = folder / FILENAME
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2048:
        raise ValueError("missing or invalid restricted materializer credential")
    dsn = path.read_text(encoding="utf-8").strip()
    if not dsn or any(ord(c) < 32 or ord(c) == 127 for c in dsn):
        raise ValueError("restricted materializer credential is invalid")
    try:
        from psycopg.conninfo import conninfo_to_dict
        config = conninfo_to_dict(dsn)
    except Exception:
        raise ValueError("restricted materializer credential parse failure") from None
    if (
        config.get("user") != LOGIN
        or config.get("dbname") != "empiredb"
        or not config.get("password")
        or config.get("service")
        or config.get("options")
    ):
        raise ValueError("dedicated materializer identity/database required")
    if config.get("host") not in ("127.0.0.1", "localhost", "::1", "/var/run/postgresql"):
        raise ValueError("nonlocal materializer endpoint rejected")
    if set(config) - {"user", "password", "dbname", "host", "port"}:
        raise ValueError("materializer connection parameter override forbidden")
    return dsn


def main() -> int:
    try:
        dsn = validated_credential(os.environ.get("CREDENTIALS_DIRECTORY"))
    except Exception:
        print(json.dumps({"ok": False, "status": "RESTRICTED_CREDENTIAL_NOT_READY",
                          "execution_authority": "none"}))
        return 3
    os.environ[KEY] = dsn
    try:
        from scripts.build_market_sweep_snapshot import main as run_read
        market_result = run_read()
        if market_result != 0:
            return market_result
        # PASS/FAIL of the *optional* TAM catalog is never permission to read
        # TAM market rows; it cannot disrupt healthy Market GPS operation.
        if _real_protected_market_gps_execution(
            os.environ.get("CREDENTIALS_DIRECTORY")
        ):
            try:
                _persist_tam_probe(_safe_probe_tam_catalog(dsn))
            except Exception:
                print(json.dumps({
                    "tam_catalog_probe": "NONBLOCKING_PROBE_NOT_PERSISTED",
                    "market_gps_result_unchanged": True,
                    "execution_authority": "none",
                }))
        return market_result
    finally:
        os.environ.pop(KEY, None)


if __name__ == "__main__":
    raise SystemExit(main())
