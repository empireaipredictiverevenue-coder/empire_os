"""Bounded EmpireOS runtime canary for the EmpireDB candidate via PgBouncer.

The canary does not change the canonical backend. It creates an in-process
EmpireDB gateway pointed at PgBouncer, exercises a representative read, then
runs the existing rollback-only commercial functional canary through the same
pool. The commercial transaction is always rolled back.
"""
from __future__ import annotations

import json
import os
from typing import Any, Callable, Mapping

from empire_os.canonical_data_gateway import gateway_from_environment
from empire_os.data_cloud_functional_canary import run_canary


def pool_dsn(dsn: str) -> str:
    from psycopg.conninfo import conninfo_to_dict, make_conninfo

    params = conninfo_to_dict(dsn)
    params["port"] = "6432"
    return make_conninfo(**params)


def run_runtime_canary(
    environ: Mapping[str, str] | None = None,
    *,
    gateway_factory: Callable[..., Any] = gateway_from_environment,
    functional_canary: Callable[[str], Mapping[str, Any]] = run_canary,
) -> dict[str, Any]:
    source = dict(os.environ if environ is None else environ)
    direct_dsn = str(source.get("EMPIREDB_DSN") or "").strip()
    if not direct_dsn:
        raise RuntimeError("EMPIREDB_DSN is required")

    canonical_before = str(
        source.get("EMPIRE_DATA_BACKEND") or "supabase_legacy"
    ).strip()
    pooled_dsn = pool_dsn(direct_dsn)

    candidate_env = dict(source)
    candidate_env["EMPIRE_DATA_BACKEND"] = "empiredb"
    candidate_env["EMPIREDB_DSN"] = pooled_dsn

    gateway = gateway_factory(candidate_env)
    if gateway.backend.value != "empiredb":
        raise RuntimeError("candidate gateway did not select EmpireDB")

    prospects_before = int(gateway.count("prospects"))
    commercial = dict(functional_canary(pooled_dsn))
    prospects_after = int(gateway.count("prospects"))

    canonical_after = str(
        source.get("EMPIRE_DATA_BACKEND") or "supabase_legacy"
    ).strip()

    rollback_verified = commercial.get("rollback_only") is True
    canonical_unchanged = canonical_before == canonical_after
    read_path_verified = prospects_before >= 0 and prospects_after == prospects_before
    commercial_verified = commercial.get("verified") is True

    verified = bool(
        read_path_verified
        and commercial_verified
        and rollback_verified
        and canonical_unchanged
    )

    return {
        "schema_version": "empire.data-cloud-runtime-canary.v1",
        "read_only_observation": True,
        "pgbouncer_port": 6432,
        "candidate_backend": "empiredb",
        "canonical_backend_before": canonical_before,
        "canonical_backend_after": canonical_after,
        "canonical_backend_unchanged": canonical_unchanged,
        "prospects_before": prospects_before,
        "prospects_after": prospects_after,
        "representative_read_verified": read_path_verified,
        "rollback_only_write_path_verified": rollback_verified,
        "commercial_canary_verified": commercial_verified,
        "functional_canary": commercial,
        "verified": verified,
        "production_cutover_authority": False,
        "authority": {
            "canonical_backend_change": False,
            "persistent_database_write": False,
            "external_send": False,
            "fund_movement": False,
            "revenue_recognition": False,
        },
    }


def main() -> int:
    report = run_runtime_canary()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["verified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
