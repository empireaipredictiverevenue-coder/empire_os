"""Local cumulative inventory ledger for legacy permit recovery.

This module never writes to Supabase. It persists only under runtime/recovery
so long-running OBSERVE scans can report cumulative unique inventory counts
without promoting recovered records into canonical production tables.
"""
from __future__ import annotations

import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any, Mapping


DB_PATH = Path("runtime/recovery/legacy_permit_inventory.sqlite3")
SUMMARY_PATH = Path("runtime/recovery/legacy_permit_inventory_summary.json")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _borough_from_address(value: Any) -> str:
    address = _text(value)
    if not address:
        return ""
    tail = address.rsplit(",", 1)[-1].strip().casefold()
    mapping = {
        "queens": "Queens",
        "brooklyn": "Brooklyn",
        "manhattan": "Manhattan",
        "bronx": "Bronx",
        "staten island": "Staten Island",
    }
    return mapping.get(tail, "")


def _open(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        create table if not exists inventory (
            legacy_prospect_id text primary key,
            recovery_classification text not null,
            recovery_state text not null,
            inventory_identity_mode text not null,
            niche text,
            metro text,
            borough text,
            permit_number text,
            owner_name text,
            source_owner_identity_state text,
            source_freshness text,
            canonical_prospect_id text,
            updated_at text not null
        )
        """
    )
    conn.execute(
        """
        create table if not exists metadata (
            key text primary key,
            value text not null
        )
        """
    )
    conn.commit()
    return conn


def _meta(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute(
        "select value from metadata where key = ?",
        (key,),
    ).fetchone()
    return str(row["value"]) if row else None


def _set_meta(conn: sqlite3.Connection, key: str, value: Any) -> None:
    conn.execute(
        """
        insert into metadata(key, value) values(?, ?)
        on conflict(key) do update set value = excluded.value
        """,
        (key, str(value)),
    )


def _count_by(conn: sqlite3.Connection, column: str) -> dict[str, int]:
    allowed = {
        "recovery_classification",
        "recovery_state",
        "inventory_identity_mode",
        "niche",
        "metro",
        "borough",
        "source_owner_identity_state",
    }
    if column not in allowed:
        raise ValueError("unsupported inventory summary column")

    rows = conn.execute(
        f"""
        select coalesce(nullif(trim({column}), ''), '<UNKNOWN>') as key,
               count(*) as n
        from inventory
        group by 1
        order by n desc, key asc
        """
    ).fetchall()
    return {str(row["key"]): int(row["n"]) for row in rows}


def _scalar(conn: sqlite3.Connection, sql: str) -> int:
    row = conn.execute(sql).fetchone()
    return int(row[0] if row else 0)


def update_cumulative_inventory(
    repo_root: str | Path,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Upsert one OBSERVE batch into the local cumulative inventory ledger."""
    if payload.get("mode") != "OBSERVE":
        raise RuntimeError("cumulative_inventory_requires_observe_mode")

    for field in (
        "database_write_performed",
        "canonical_promotion_performed",
        "outbound_sent",
        "actual_revenue",
    ):
        if payload.get(field) is not False:
            raise RuntimeError(f"unsafe_recovery_payload:{field}")

    root = Path(repo_root).resolve()
    db_path = root / DB_PATH
    summary_path = root / SUMMARY_PATH
    scan_epoch = _text(payload.get("scan_epoch"))
    scan_order = _text(payload.get("scan_order"))

    conn = _open(db_path)
    try:
        prior_epoch = _meta(conn, "scan_epoch")
        prior_order = _meta(conn, "scan_order")

        reset = bool(
            (prior_epoch and prior_epoch != scan_epoch)
            or (prior_order and prior_order != scan_order)
        )
        if reset:
            conn.execute("delete from inventory")
            conn.execute("delete from metadata")
            conn.commit()

        for record in payload.get("records") or []:
            if not isinstance(record, Mapping):
                continue
            legacy_id = _text(record.get("legacy_prospect_id"))
            if not legacy_id:
                continue
            fields = record.get("recovered_fields") or {}
            original = record.get("original_evidence") or {}
            conn.execute(
                """
                insert into inventory(
                    legacy_prospect_id,
                    recovery_classification,
                    recovery_state,
                    inventory_identity_mode,
                    niche,
                    metro,
                    borough,
                    permit_number,
                    owner_name,
                    source_owner_identity_state,
                    source_freshness,
                    canonical_prospect_id,
                    updated_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(legacy_prospect_id) do update set
                    recovery_classification = excluded.recovery_classification,
                    recovery_state = excluded.recovery_state,
                    inventory_identity_mode = excluded.inventory_identity_mode,
                    niche = excluded.niche,
                    metro = excluded.metro,
                    borough = excluded.borough,
                    permit_number = excluded.permit_number,
                    owner_name = excluded.owner_name,
                    source_owner_identity_state =
                        excluded.source_owner_identity_state,
                    source_freshness = excluded.source_freshness,
                    canonical_prospect_id = excluded.canonical_prospect_id,
                    updated_at = excluded.updated_at
                """,
                (
                    legacy_id,
                    _text(record.get("recovery_classification")),
                    _text(record.get("recovery_state")),
                    _text(record.get("inventory_identity_mode")),
                    _text(original.get("niche")),
                    _text(fields.get("metro") or original.get("metro")),
                    _borough_from_address(fields.get("address")),
                    _text(fields.get("permit_number")),
                    _text(fields.get("business_name")),
                    _text(record.get("source_owner_identity_state")),
                    _text(record.get("source_freshness")),
                    _text(record.get("canonical_prospect_id")),
                    _text(payload.get("generated_at")),
                ),
            )

        cycles = int(_meta(conn, "cycles") or 0) + 1
        full_scan_completions = int(
            _meta(conn, "full_scan_completions") or 0
        )
        latest_cycle_completed_scan = bool(
            int(payload.get("next_offset") or 0) == 0
            and int(payload.get("scanned_row_count") or 0) > 0
        )
        if latest_cycle_completed_scan:
            full_scan_completions += 1

        _set_meta(conn, "cycles", cycles)
        _set_meta(
            conn,
            "full_scan_completions",
            full_scan_completions,
        )
        _set_meta(conn, "scan_epoch", scan_epoch)
        _set_meta(conn, "scan_order", scan_order)
        _set_meta(conn, "last_scan_offset", payload.get("scan_offset") or 0)
        _set_meta(conn, "last_next_offset", payload.get("next_offset") or 0)
        _set_meta(conn, "last_generated_at", payload.get("generated_at") or "")
        conn.commit()

        total = _scalar(conn, "select count(*) from inventory")
        verified_current = _scalar(
            conn,
            """
            select count(*) from inventory
            where recovery_state in (
                'VERIFIED_CURRENT',
                'VERIFIED_CURRENT_PROJECT_ONLY'
            )
            """,
        )
        owner_verified = _scalar(
            conn,
            """
            select count(*) from inventory
            where recovery_state = 'VERIFIED_CURRENT'
              and inventory_identity_mode = 'OWNER_IDENTIFIED'
            """,
        )
        project_only_verified = _scalar(
            conn,
            """
            select count(*) from inventory
            where recovery_state = 'VERIFIED_CURRENT_PROJECT_ONLY'
              and inventory_identity_mode = 'PROJECT_ONLY'
            """,
        )
        merge_candidates = _scalar(
            conn,
            """
            select count(*) from inventory
            where recovery_classification = 'MERGE'
            """,
        )
        reuse_candidates = _scalar(
            conn,
            """
            select count(*) from inventory
            where recovery_classification = 'REUSE'
            """,
        )

        summary = {
            "schema_version": "empire.legacy-permit-inventory.v1",
            "mode": "OBSERVE",
            "scan_epoch": scan_epoch,
            "scan_order": scan_order,
            "cycles": cycles,
            "unique_inventory_records": total,
            "verified_current_inventory": verified_current,
            "verified_current_owner_identified": owner_verified,
            "verified_current_project_only": project_only_verified,
            "merge_candidates": merge_candidates,
            "reuse_candidates": reuse_candidates,
            "classification_counts": _count_by(
                conn, "recovery_classification"
            ),
            "recovery_state_counts": _count_by(conn, "recovery_state"),
            "inventory_identity_mode_counts": _count_by(
                conn, "inventory_identity_mode"
            ),
            "niche_counts": _count_by(conn, "niche"),
            "metro_counts": _count_by(conn, "metro"),
            "borough_counts": _count_by(conn, "borough"),
            "source_owner_identity_counts": _count_by(
                conn, "source_owner_identity_state"
            ),
            "last_scan_offset": int(payload.get("scan_offset") or 0),
            "next_offset": int(payload.get("next_offset") or 0),
            "latest_cycle_completed_scan": latest_cycle_completed_scan,
            "full_scan_completions": full_scan_completions,
            "full_scan_complete": full_scan_completions > 0,
            "canonical_database_write_performed": False,
            "canonical_promotion_performed": False,
            "outbound_sent": False,
            "actual_revenue": False,
            "local_runtime_inventory_write_performed": True,
        }

        tmp = summary_path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        tmp.replace(summary_path)
        return summary
    finally:
        conn.close()
