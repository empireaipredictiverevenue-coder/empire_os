"""Dedicated EmpireDB PostgreSQL custody transport; no public API.

All writes require an explicitly provisioned dedicated custodian LOGIN
with membership in the NOLOGIN data-exchange role. No generic empiredb_app,
no privileged sudo, no bypass and NO live migration from this code.
One capture per explicit one-shot invocation; no pollers or timers.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping

from empire_os.data_exchange_observation_custody import (
    CustodyIntegrityError, MAX_BOARD_HISTORY,
    parse_at, plan_custody_append, verify_custody_window,
)
from empire_os.data_exchange_signal_board import build_signal_board

TABLE = "public.empire_data_exchange_observations"
COLUMN_NAMES = (
    "sequence", "schema_version", "source_id", "dataset_id", "region",
    "source_observed_at", "snapshot_sha256", "previous_chain_sha256",
    "chain_sha256", "snapshot_json",
)
SELECT_COLUMNS = (
    "sequence, schema_version, source_id, dataset_id, region, "
    "source_observed_at, snapshot_sha256, previous_chain_sha256, "
    "chain_sha256, snapshot_json"
)
LOCK_KEY = 510218720
ROLE = "empire_data_exchange_custodian"


class CustodyTransportError(RuntimeError):
    """Database state is unavailable or untrusted; never retry blindly."""


def _dict_row(record: Any) -> dict[str, Any]:
    if not isinstance(record, (list, tuple)) or len(record) != len(COLUMN_NAMES):
        raise CustodyIntegrityError("database row shape invalid")
    result = dict(zip(COLUMN_NAMES, record, strict=True))
    if isinstance(result["source_observed_at"], datetime):
        result["source_observed_at"] = result["source_observed_at"].isoformat()
    return result


class EmpireDBConstructionCustody:
    def __init__(self, dsn: str, *, connector: Callable | None = None):
        if not isinstance(dsn, str) or not dsn.strip():
            raise CustodyTransportError("dedicated Data Exchange DSN is missing")
        if connector is None:
            import psycopg
            connector = psycopg.connect
        self._connect = connector
        self._dsn = dsn

    def append_once(self, snapshot: Mapping[str, Any], *, now: datetime) -> dict[str, Any]:
        """Serialize first-party observations, recheck head and write once.

        The DB UNIQUE index and advisory transaction lock protect against
        concurrent head advances. A connection/commit failure is UNCERTAIN;
        an external operator must read the canonical head before retrying.
        """
        if now.tzinfo is None or now.utcoffset() is None:
            raise CustodyIntegrityError("current time requires timezone")
        try:
            from psycopg.types.json import Jsonb
            with self._connect(self._dsn, connect_timeout=5) as conn:
                with conn.cursor() as cur:
                    cur.execute("SET LOCAL statement_timeout = '5000ms'")
                    cur.execute("SET LOCAL lock_timeout = '3000ms'")
                    cur.execute(f"SET LOCAL ROLE {ROLE}")
                    cur.execute("SELECT pg_advisory_xact_lock(%s)", (LOCK_KEY,))
                    cur.execute(f"SELECT {SELECT_COLUMNS} FROM {TABLE} ORDER BY sequence DESC LIMIT 1")
                    fetched = cur.fetchone()
                    preceding = _dict_row(fetched) if fetched is not None else None
                    plan = plan_custody_append(snapshot, previous=preceding, assessed_at=now)
                    if plan["mode"] == "DUPLICATE_EXACT_SNAPSHOT_NO_WRITE":
                        return {
                            "mode": "ALREADY_OBSERVED",
                            "sequence": plan["sequence"],
                            "head_chain_sha256": plan["chain_sha256"],
                            "database_writes": False,
                            "customer_delivery_enabled": False,
                            "execution_authority": "NONE",
                        }
                    entry = plan["row"]
                    # V16 temporal guard is enforced INSIDE the existing
                    # serialised writer, not just in a separate CLI check.
                    # A manually started legacy V15 oneshot cannot bypass it.
                    # Exact same-timestamp replays remain a prior no-op.
                    if preceding is not None and (
                        parse_at(entry["source_observed_at"])
                        - parse_at(preceding["source_observed_at"])
                        < timedelta(hours=24)
                    ):
                        raise CustodyIntegrityError(
                            "CANONICAL_NEXT_OBSERVATION_NOT_DUE_24H"
                        )
                    cur.execute(
                        f"INSERT INTO {TABLE} "
                        "(sequence,schema_version,source_id,dataset_id,region,"
                        "source_observed_at,snapshot_sha256,previous_chain_sha256,"
                        "chain_sha256,snapshot_json) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                        "RETURNING sequence,chain_sha256",
                        (
                            entry["sequence"],entry["schema_version"],
                            entry["source_id"],entry["dataset_id"],entry["region"],
                            entry["source_observed_at"],entry["snapshot_sha256"],
                            entry["previous_chain_sha256"],entry["chain_sha256"],
                            Jsonb(entry["snapshot_json"]),
                        ),
                    )
                    receipt = cur.fetchone()
                    if receipt != (entry["sequence"], entry["chain_sha256"]):
                        raise CustodyTransportError("canonical insert receipt mismatch")
            return {
                "mode": "CANONICAL_APPEND_COMMITTED",
                "sequence": entry["sequence"],
                "head_chain_sha256": entry["chain_sha256"],
                "database_writes": True,
                "external_anchor_verified": False,
                "customer_delivery_enabled": False,
                "execution_authority": "NONE",
            }
        except (CustodyIntegrityError, CustodyTransportError):
            raise
        except Exception as exc:
            # A five-character PostgreSQL SQLSTATE is safe diagnostic data;
            # never log the DSN, SQL text, source payload, or exception body.
            state = getattr(exc, "sqlstate", None)
            suffix = (":" + state if isinstance(state, str)
                      and len(state) == 5 and state.isalnum() else "")
            raise CustodyTransportError(
                "CANONICAL_DB_TRANSACTION_UNAVAILABLE_OR_UNCERTAIN" + suffix
            ) from None

    def read_window(self) -> list[dict[str, Any]]:
        """Only the 16 most recent canonical observations; never alter DB."""
        try:
            with self._connect(self._dsn, connect_timeout=5) as conn:
                with conn.cursor() as cur:
                    cur.execute("SET TRANSACTION READ ONLY")
                    cur.execute("SET LOCAL statement_timeout = '5000ms'")
                    cur.execute(f"SET LOCAL ROLE {ROLE}")
                    cur.execute(
                        f"SELECT {SELECT_COLUMNS} FROM {TABLE} "
                        "ORDER BY sequence DESC LIMIT %s",
                        (MAX_BOARD_HISTORY,),
                    )
                    rows = [_dict_row(row) for row in cur.fetchall()]
            return list(reversed(rows))
        except (CustodyIntegrityError, CustodyTransportError):
            raise
        except Exception:
            raise CustodyTransportError("CANONICAL_DB_READ_UNAVAILABLE") from None

    def read_signal_board(self, *, now: datetime, limit: int = 24) -> dict[str, Any]:
        rows = self.read_window()
        if len(rows) < 2:
            return {
                "mode": "OBSERVE",
                "feed_status": "HOLD_NEED_TWO_CANONICAL_OBSERVATIONS",
                "canonical_observation_count_in_window": len(rows),
                "customer_delivery_enabled": False,
                "data_resale_authorized": False,
                "production_writes": False,
                "execution_authority": "NONE",
            }
        proof = verify_custody_window(rows)
        board = build_signal_board(
            source_snapshots=[row["snapshot_json"] for row in rows],
            procurement=None, assessed_at=now, limit=limit,
        )
        if board["customer_delivery_enabled"] is not False:
            raise CustodyIntegrityError("signal board authority mismatch")
        board["canonical_custody"] = proof
        # The signal board history SHA is local to the last 16 snapshots
        # when the DB has more than 16. Do not conflate with global DB head.
        board["custody_window_is_complete_chain"] = proof["window_origin_anchored_to_genesis"]
        return board
