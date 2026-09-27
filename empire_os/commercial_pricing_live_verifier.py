"""Verify live commercial catalog pricing against founder-approved policy."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from empire_os.commercial_pricing_policy import (
    APPROVAL_REFERENCE,
    LAUNCH_PRICING,
)


OUTPUT = Path("runtime/commercial_catalog/pricing_verification_latest.json")


def _expected() -> dict[str, dict[str, Any]]:
    rows = {
        policy.product_code: {
            "billing_model": policy.billing_model,
            "amount_cents": policy.amount_cents,
            "unit": policy.unit,
            "approval_reference": APPROVAL_REFERENCE,
        }
        for policy in LAUNCH_PRICING
    }
    rows["managed_service"] = {
        "billing_model": "flat_pilot",
        "amount_cents": 150000,
        "unit": "flat",
        "approval_reference": None,
    }
    return rows


def verify_catalog_snapshot(
    snapshot: Mapping[str, Any],
    *,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    products = {
        str(row.get("product_code") or ""): dict(row)
        for row in (snapshot.get("products") or [])
        if isinstance(row, Mapping)
        and str(row.get("product_code") or "")
    }

    checks: list[dict[str, Any]] = []
    drift_count = 0
    missing_count = 0

    for code, expected in sorted(_expected().items()):
        row = products.get(code)
        if row is None:
            missing_count += 1
            drift_count += 1
            checks.append({
                "product_code": code,
                "state": "MISSING",
                "matches_policy": False,
            })
            continue

        price_basis = (
            dict(row.get("price_basis"))
            if isinstance(row.get("price_basis"), Mapping)
            else {}
        )
        amount = price_basis.get("amount_cents")
        unit = price_basis.get("unit")
        approval = price_basis.get("approval_reference")

        matches = (
            row.get("catalog_state") == "VERIFIED"
            and row.get("version_state") == "VERIFIED"
            and row.get("binding_terms_ready") is True
            and row.get("billing_model") == expected["billing_model"]
            and amount == expected["amount_cents"]
            and unit == expected["unit"]
            and (
                expected["approval_reference"] is None
                or approval == expected["approval_reference"]
            )
        )
        if not matches:
            drift_count += 1

        checks.append({
            "product_code": code,
            "state": "MATCH" if matches else "DRIFT",
            "matches_policy": matches,
            "catalog_state": row.get("catalog_state"),
            "version_state": row.get("version_state"),
            "binding_terms_ready": row.get("binding_terms_ready"),
            "billing_model": row.get("billing_model"),
            "amount_cents": amount,
            "unit": unit,
            "approval_reference": approval,
            "expected_amount_cents": expected["amount_cents"],
            "expected_unit": expected["unit"],
            "expected_billing_model": expected["billing_model"],
        })

    now = observed_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("observed_at must include timezone")

    return {
        "schema_version": "empire.commercial_pricing_verification.v1",
        "observed_at": now.astimezone(timezone.utc).isoformat(),
        "approval_reference": APPROVAL_REFERENCE,
        "expected_product_count": len(_expected()),
        "checked_product_count": len(checks),
        "missing_product_count": missing_count,
        "drift_count": drift_count,
        "pricing_matches_approved_policy": drift_count == 0,
        "checks": checks,
        "actual_revenue": False,
        "execution_authority": "none",
    }


def refresh_pricing_verification(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    catalog_path = root / "runtime/commercial_catalog/latest.json"
    try:
        snapshot = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        snapshot = {}
    if not isinstance(snapshot, dict):
        snapshot = {}

    payload = verify_catalog_snapshot(snapshot)
    path = root / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return payload
