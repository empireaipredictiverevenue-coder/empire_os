"""Read-only pgBackRest observation for Empire Data Cloud.

Runs as the postgres OS user in its own hardened systemd oneshot service.
It never creates a backup, restores data, changes WAL settings, changes the
canonical backend, or exposes repository secrets. The only write is a sanitized
runtime health snapshot under /run.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
from typing import Any, Mapping


PGBACKREST_CONFIG = Path("/etc/pgbackrest/empiredb.conf")
PGBACKREST_STANZA = "empiredb"
DEFAULT_OUTPUT = Path("/run/empire-data-cloud/pgbackrest.json")


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _config_snapshot(path: Path = PGBACKREST_CONFIG) -> dict[str, Any]:
    result: dict[str, Any] = {
        "repo_type": None,
        "repo_path": None,
        "cipher_type": None,
    }
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return result

    for raw in lines:
        text = raw.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, value = text.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key == "repo1-type":
            result["repo_type"] = value
        elif key == "repo1-path":
            result["repo_path"] = value
        elif key == "repo1-cipher-type":
            result["cipher_type"] = value
    return result


def observe_pgbackrest(
    *,
    runner=subprocess.run,
    config_path: Path = PGBACKREST_CONFIG,
) -> dict[str, Any]:
    config = _config_snapshot(config_path)
    completed = runner(
        [
            "pgbackrest",
            f"--config={config_path}",
            f"--stanza={PGBACKREST_STANZA}",
            "--log-level-file=off",
            "--output=json",
            "info",
        ],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    base = {
        "schema_version": "empire.pgbackrest-observation.v1",
        "observed_at": _iso_now(),
        "read_only": True,
        "backup_creation": False,
        "restore_performed": False,
        "production_cutover_authority": False,
        **config,
    }

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").lower()
        if "permission denied" in detail:
            failure = "PgBackRestPermissionDenied"
        elif "not found" in detail or "no such file" in detail:
            failure = "PgBackRestPathMissing"
        elif "config" in detail and "error" in detail:
            failure = "PgBackRestConfigError"
        else:
            failure = "PgBackRestInfoFailed"
        return {
            **base,
            "healthy": False,
            "backup_count": 0,
            "latest_label": None,
            "error_class": failure,
            "returncode": int(completed.returncode),
            "off_node_repository_verified": False,
        }

    try:
        payload = json.loads(completed.stdout or "[]")
    except json.JSONDecodeError:
        return {
            **base,
            "healthy": False,
            "backup_count": 0,
            "latest_label": None,
            "error_class": "InvalidPgBackRestJson",
            "off_node_repository_verified": False,
        }

    stanza = payload[0] if isinstance(payload, list) and payload else {}
    status = stanza.get("status") if isinstance(stanza, Mapping) else {}
    backups = stanza.get("backup") if isinstance(stanza, Mapping) else []
    backups = backups if isinstance(backups, list) else []
    latest = backups[-1] if backups else {}
    status_code = status.get("code") if isinstance(status, Mapping) else None

    return {
        **base,
        "healthy": status_code == 0 and bool(backups),
        "status_code": status_code,
        "backup_count": len(backups),
        "latest_label": (
            latest.get("label") if isinstance(latest, Mapping) else None
        ),
        "encrypted": config.get("cipher_type") == "aes-256-cbc",
        # The current repository is local by design. Do not infer off-node
        # durability from a healthy local backup.
        "off_node_repository_verified": False,
    }


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(tmp, 0o640)
    tmp.replace(path)
    os.chmod(path, 0o640)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    report = observe_pgbackrest()
    _atomic_json(Path(args.output), report)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["healthy"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
