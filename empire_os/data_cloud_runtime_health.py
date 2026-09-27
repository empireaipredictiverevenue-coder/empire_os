"""Read-only runtime health probe for Empire Data Cloud.

This module is infrastructure observability, not application data access.
It is designed to run inside the existing root-owned privileged helper so the
unprivileged Reliability Agent never receives EmpireDB credentials.

No writes, schema changes, cutover actions, service restarts, backup creation,
WAL changes, or authority expansion are performed here.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Any, Callable, Mapping


EMPIREDB_ENV = Path("/etc/empiredb.env")
EMPIRE_OS_ENV = Path("/etc/empire_os.env")
PGBACKREST_CONFIG = Path("/etc/pgbackrest/empiredb.conf")
PGBACKREST_STANZA = "empiredb"
PGBACKREST_OBSERVER_UNIT = "empire-data-cloud-backup-observer.service"
PGBACKREST_OBSERVER_SNAPSHOT = Path(
    "/run/empire-data-cloud/pgbackrest.json"
)

POSTGRES_UNIT = "postgresql@18-main"
PGBOUNCER_UNIT = "pgbouncer"

Runner = Callable[..., Any]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return values

    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value[:1] == value[-1:] and value[:1] in {"'", '"'}:
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def _systemctl_active(unit: str, *, runner: Runner = subprocess.run) -> dict[str, Any]:
    completed = runner(
        ["systemctl", "is-active", unit],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    state = (completed.stdout or completed.stderr or "").strip() or "unknown"
    return {
        "unit": unit,
        "active": completed.returncode == 0 and state == "active",
        "state": state,
    }


def _pool_dsn(dsn: str) -> str:
    try:
        from psycopg.conninfo import conninfo_to_dict, make_conninfo
    except ImportError as exc:
        raise RuntimeError("psycopg is required for EmpireDB health") from exc

    params = conninfo_to_dict(dsn)
    params["port"] = "6432"
    return make_conninfo(**params)


def _postgres_probe(dsn: str, *, application_name: str) -> dict[str, Any]:
    if not str(dsn or "").strip():
        return {
            "healthy": False,
            "database": None,
            "in_recovery": None,
            "archive_mode": None,
            "prospects_visible": None,
            "error_class": "DSNNotConfigured",
        }

    connection = None
    try:
        import psycopg

        connection = psycopg.connect(
            dsn,
            connect_timeout=5,
            application_name=application_name,
        )
        connection.execute("SET statement_timeout = '5s'")
        row = connection.execute(
            """
            SELECT current_database(),
                   pg_is_in_recovery(),
                   current_setting('archive_mode'),
                   (SELECT count(*) FROM public.prospects)
            """
        ).fetchone()
        return {
            "healthy": True,
            "database": str(row[0]) if row else None,
            "in_recovery": bool(row[1]) if row else None,
            "archive_mode": str(row[2]) if row else None,
            "prospects_visible": int(row[3]) if row else None,
        }
    except Exception as exc:
        return {
            "healthy": False,
            "database": None,
            "in_recovery": None,
            "archive_mode": None,
            "prospects_visible": None,
            "error_class": type(exc).__name__,
        }
    finally:
        if connection is not None:
            connection.close()


def _pgbackrest_config() -> dict[str, Any]:
    # pgBackRest config is INI-shaped, not env-shaped. Parse only the fixed
    # non-secret keys needed for topology reporting.
    result: dict[str, Any] = {
        "repo_type": None,
        "repo_path": None,
        "cipher_type": None,
    }
    try:
        lines = PGBACKREST_CONFIG.read_text(encoding="utf-8").splitlines()
    except OSError:
        return result

    for line in lines:
        text = line.strip()
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


def _pgbackrest_probe(*, runner: Runner = subprocess.run) -> dict[str, Any]:
    """Refresh and read the postgres-owned backup observation.

    The privileged helper starts only this fixed read-only oneshot service.
    pgBackRest itself runs as postgres in that separate systemd sandbox, so the
    helper never changes UID/GID and never receives backup repository secrets.
    """
    completed = runner(
        ["systemctl", "start", PGBACKREST_OBSERVER_UNIT],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        return {
            **_pgbackrest_config(),
            "healthy": False,
            "backup_count": 0,
            "latest_label": None,
            "error_class": "PgBackRestObserverServiceFailed",
            "returncode": int(completed.returncode),
            "off_node_repository_verified": False,
        }

    try:
        payload = json.loads(
            PGBACKREST_OBSERVER_SNAPSHOT.read_text(encoding="utf-8")
        )
    except FileNotFoundError:
        return {
            **_pgbackrest_config(),
            "healthy": False,
            "backup_count": 0,
            "latest_label": None,
            "error_class": "PgBackRestObserverSnapshotMissing",
            "off_node_repository_verified": False,
        }
    except (OSError, json.JSONDecodeError):
        return {
            **_pgbackrest_config(),
            "healthy": False,
            "backup_count": 0,
            "latest_label": None,
            "error_class": "PgBackRestObserverSnapshotInvalid",
            "off_node_repository_verified": False,
        }

    if not isinstance(payload, Mapping):
        return {
            **_pgbackrest_config(),
            "healthy": False,
            "backup_count": 0,
            "latest_label": None,
            "error_class": "PgBackRestObserverSnapshotInvalid",
            "off_node_repository_verified": False,
        }

    # Re-project only the bounded non-secret fields consumed by health state.
    return {
        "repo_type": payload.get("repo_type"),
        "repo_path": payload.get("repo_path"),
        "cipher_type": payload.get("cipher_type"),
        "healthy": payload.get("healthy") is True,
        "backup_count": int(payload.get("backup_count") or 0),
        "latest_label": payload.get("latest_label"),
        "encrypted": payload.get("encrypted") is True,
        "off_node_repository_verified": (
            payload.get("off_node_repository_verified") is True
        ),
        "error_class": payload.get("error_class"),
    }


def collect_data_cloud_health(
    *,
    runner: Runner = subprocess.run,
    empiredb_env: Path = EMPIREDB_ENV,
    empire_os_env: Path = EMPIRE_OS_ENV,
) -> dict[str, Any]:
    db_env = _read_env(empiredb_env)
    os_env = _read_env(empire_os_env)

    dsn = str(db_env.get("EMPIREDB_DSN") or "").strip()
    canonical_backend = str(
        os_env.get("EMPIRE_DATA_BACKEND") or "supabase_legacy"
    ).strip()

    postgres_service = _systemctl_active(POSTGRES_UNIT, runner=runner)
    pgbouncer_service = _systemctl_active(PGBOUNCER_UNIT, runner=runner)

    direct = _postgres_probe(
        dsn,
        application_name="empire-data-cloud-health-direct",
    )
    try:
        pool_dsn = _pool_dsn(dsn) if dsn else ""
    except Exception:
        pool_dsn = ""
    pooled = _postgres_probe(
        pool_dsn,
        application_name="empire-data-cloud-health-pool",
    )
    backup = _pgbackrest_probe(runner=runner)

    primary_ok = (
        direct.get("healthy") is True
        and direct.get("database") == "empiredb"
        and direct.get("in_recovery") is False
    )
    pool_ok = (
        pooled.get("healthy") is True
        and pooled.get("database") == "empiredb"
        and pooled.get("in_recovery") is False
    )
    candidate_runtime_healthy = bool(
        postgres_service["active"]
        and pgbouncer_service["active"]
        and primary_ok
        and pool_ok
    )

    archive_mode_on = direct.get("archive_mode") == "on"
    off_node_verified = backup.get("off_node_repository_verified") is True
    pitr_verified = bool(
        archive_mode_on
        and backup.get("healthy") is True
        and off_node_verified
    )

    open_gates: list[str] = []
    if backup.get("healthy") is not True:
        open_gates.append("local_backup_health")
    if not off_node_verified:
        open_gates.append("off_node_backup")
    if not pitr_verified:
        open_gates.append("wal_pitr")
    open_gates.extend([
        "recovery_failover_proof",
        "tenant_isolation_verification",
        "rollback_proof",
        "founder_cutover_approval",
    ])

    return {
        "schema_version": "empire.data-cloud-runtime-health.v1",
        "observed_at": _now_iso(),
        "read_only": True,
        "production_cutover_authority": False,
        "canonical_backend": canonical_backend,
        "canonical_backend_source": (
            "explicit_env"
            if os_env.get("EMPIRE_DATA_BACKEND")
            else "default_supabase_legacy"
        ),
        "empiredb_candidate_only": canonical_backend != "empiredb",
        "postgres_service": postgres_service,
        "pgbouncer_service": pgbouncer_service,
        "empiredb_direct": direct,
        "empiredb_via_pgbouncer": pooled,
        "backup": backup,
        "archive_mode_on": archive_mode_on,
        "pitr_verified": pitr_verified,
        "ha_replica_verified": False,
        "candidate_runtime_healthy": candidate_runtime_healthy,
        "operational_cutover_ready": (
            candidate_runtime_healthy
            and backup.get("healthy") is True
            and off_node_verified
            and pitr_verified
            and not open_gates
        ),
        "open_gates": open_gates,
        "authority": {
            "database_write": False,
            "schema_mutation": False,
            "service_restart": False,
            "backup_creation": False,
            "canonical_cutover": False,
            "fund_movement": False,
            "authority_expansion": False,
        },
    }


def main() -> int:
    report = collect_data_cloud_health()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["candidate_runtime_healthy"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
