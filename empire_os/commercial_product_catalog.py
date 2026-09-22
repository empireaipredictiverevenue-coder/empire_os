"""Canonical commercial product/cost catalog projections.

The database remains authoritative. This module only reads the bounded catalog
RPC, computes internal readiness summaries, and writes a read-only runtime
snapshot. It never sets prices/costs, verifies catalog versions, accepts terms,
moves funds, or recognizes revenue.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping


Request = Callable[..., Any]
CATALOG_PATH = Path(os.getenv(
    "EMPIRE_COMMERCIAL_CATALOG_LATEST",
    "/srv/empire_os/runtime/commercial_catalog/latest.json",
))


def _state(value: Any) -> str:
    if isinstance(value, Mapping):
        return str(value.get("state") or "UNKNOWN").strip().upper()
    return "UNKNOWN"


def assess_catalog_item(row: Mapping[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    if row.get("active") is not True:
        blockers.append("product_inactive")
    if str(row.get("catalog_state") or "UNKNOWN").upper() != "VERIFIED":
        blockers.append("catalog_unverified")
    if str(row.get("version_state") or "UNKNOWN").upper() != "VERIFIED":
        blockers.append("version_unverified")
    for key, blocker in (
        ("price_basis", "price_basis_unverified"),
        ("acquisition_cost_basis", "acquisition_cost_basis_unverified"),
        ("fulfilment_cost_basis", "fulfilment_cost_basis_unverified"),
        ("margin_policy", "margin_policy_unverified"),
    ):
        if _state(row.get(key)) != "VERIFIED":
            blockers.append(blocker)

    if row.get("binding_terms_ready") is False and not blockers:
        blockers.append("catalog_effective_window_inactive")

    return {
        **dict(row),
        "binding_terms_ready": not blockers,
        "readiness_blockers": blockers,
        "actual_revenue": False,
    }


def summarize_catalog(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    assessed = [assess_catalog_item(row) for row in rows]
    blocker_counts: dict[str, int] = {}
    for row in assessed:
        for blocker in row["readiness_blockers"]:
            blocker_counts[blocker] = blocker_counts.get(blocker, 0) + 1
    return {
        "schema_version": "empire.commercial-product-catalog.v1",
        "product_count": len(assessed),
        "active_count": sum(row.get("active") is True for row in assessed),
        "binding_terms_ready_count": sum(
            row["binding_terms_ready"] is True for row in assessed
        ),
        "blocker_counts": dict(sorted(blocker_counts.items())),
        "products": assessed,
        "actual_revenue": False,
        "execution_authority": "none",
    }


def fetch_catalog(
    request: Request,
    *,
    product_code: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    bounded = max(1, min(int(limit), 500))
    payload = {
        "p_product_code": product_code,
        "p_limit": bounded,
    }
    rows = request(
        "POST",
        "/rest/v1/rpc/get_commercial_product_catalog",
        payload=payload,
    ) or []
    if isinstance(rows, Mapping):
        rows = [rows]
    if not isinstance(rows, list):
        raise ValueError("commercial product catalog RPC must return a list")
    clean = [row for row in rows if isinstance(row, Mapping)]
    return summarize_catalog(clean)


def write_catalog_snapshot(
    snapshot: Mapping[str, Any],
    path: str | Path | None = None,
) -> Path:
    target = Path(path or CATALOG_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(dict(snapshot), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(tmp, 0o600)
    tmp.replace(target)
    os.chmod(target, 0o600)
    return target


def public_catalog_projection(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    products: list[dict[str, Any]] = []
    for row in snapshot.get("products") or []:
        if not isinstance(row, Mapping):
            continue
        if row.get("active") is not True:
            continue
        if str(row.get("catalog_state") or "").upper() != "VERIFIED":
            continue
        if str(row.get("version_state") or "").upper() != "VERIFIED":
            continue
        if row.get("binding_terms_ready") is not True:
            continue

        price_basis = row.get("price_basis")
        public_price = {}
        if isinstance(price_basis, Mapping) and _state(price_basis) == "VERIFIED":
            public_price = {
                key: price_basis.get(key)
                for key in ("unit", "amount_cents", "currency", "billing_model")
                if price_basis.get(key) is not None
            }

        products.append({
            "product_code": row.get("product_code"),
            "product_name": row.get("product_name"),
            "product_family": row.get("product_family"),
            "billing_model": row.get("billing_model"),
            "currency": row.get("currency"),
            "version": row.get("version"),
            "binding_terms_ready": row.get("binding_terms_ready") is True,
            "price": public_price,
        })

    return {
        "status": "live" if products else "canonical_catalog_empty",
        "products": products,
        "count": len(products),
    }



def fetch_catalog_postgres(
    dsn: str,
    *,
    product_code: str | None = None,
    limit: int = 100,
    connect_factory: Callable | None = None,
) -> dict[str, Any]:
    """Read canonical catalog through the restricted materializer connection.

    This is read-only. The database RPC remains authoritative and the caller
    receives the same summarized projection as the PostgREST path.
    """
    bounded = max(1, min(int(limit), 500))
    dsn = str(dsn or "").strip()
    if not dsn:
        raise ValueError("materializer database dsn required")

    if connect_factory is None:
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError(
                "psycopg is required for direct catalog refresh"
            ) from exc
        connect_factory = psycopg.connect

    try:
        with connect_factory(dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SET LOCAL ROLE empire_intelligence_materializer"
                )
                cursor.execute(
                    "SELECT public.get_commercial_product_catalog(%s,%s)",
                    (product_code, bounded),
                )
                row = cursor.fetchone()
    except Exception as exc:
        raise RuntimeError(
            "restricted catalog read failed"
        ) from exc

    payload = row[0] if row else []
    if isinstance(payload, Mapping):
        payload = [payload]
    if not isinstance(payload, list):
        raise ValueError(
            "commercial product catalog RPC must return a list"
        )
    clean = [item for item in payload if isinstance(item, Mapping)]
    return summarize_catalog(clean)
