"""Read-only canonical catalogue evidence/readiness projection, not a checkout.

Checks root-owned local snapshot custody and existing canonical blocker rules.
No original database read, tenant authentication, customer outcome or pricing
authority is manufactured from the local snapshot.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import os
import stat
from typing import Any, Mapping

from empire_os.commercial_product_catalog import assess_catalog_item
from empire_os.predictive_catalog_intelligence_contracts import (
    ProductContractHold, build_catalogue_intelligence_contracts, LANES,
)
from empire_os.predictive_revenue_products import PREDICTIVE_REVENUE_PRODUCTS

SCHEMA = "empire.predictive_revenue.catalog_original_readiness.v1"
ROOT_CATALOGUE = Path("/srv/empire_os/runtime/commercial_catalog/latest.json")
MAX_SOURCE_BYTES = 700_000
MAX_AGE_SECONDS = 36 * 3600
MAX_CLOCK_SKEW_SECONDS = 300
CUSTODY_STATUS = "ROOT_OWNED_LOCAL_SNAPSHOT_ONLY_NOT_DB_PROOF"


def _stamp(value: Any) -> datetime:
    if type(value) is not str:
        raise ProductContractHold("catalogue generated_at absent")
    try:
        t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ProductContractHold("catalogue generated_at invalid") from None
    if t.tzinfo is None or t.utcoffset() is None:
        raise ProductContractHold("catalogue generated_at must be timezone aware")
    return t.astimezone(timezone.utc)


def _count(value: Any, limit: int) -> int:
    if type(value) is not int or not 0 <= value <= limit:
        raise ProductContractHold("untrusted catalogue count")
    return value


def _review_catalogue(catalogue: Mapping[str, Any], *, as_of: datetime) -> dict[str, Any]:
    """Independently reconcile product-level catalogue blockers before mapping."""
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ProductContractHold("timezone aware review timestamp required")
    now = as_of.astimezone(timezone.utc)
    contracts = build_catalogue_intelligence_contracts(catalogue)
    source_time = _stamp(catalogue.get("generated_at"))
    age = (now - source_time).total_seconds()
    if not -MAX_CLOCK_SKEW_SECONDS <= age <= MAX_AGE_SECONDS:
        raise ProductContractHold("catalogue source stale or future dated")
    if catalogue.get("execution_authority") != "none" or catalogue.get("actual_revenue") is not False:
        raise ProductContractHold("catalogue tried to assert financial authority")
    source_rows = catalogue["products"]
    if _count(catalogue.get("active_count"), len(source_rows)) != sum(
        row.get("active") is True for row in source_rows
    ):
        raise ProductContractHold("catalogue active_count mismatches original records")
    blocker_count: Counter[str] = Counter()
    index: dict[str, Mapping[str, Any]] = {}
    for row in source_rows:
        original = assess_catalog_item(row)
        if original["binding_terms_ready"] is not row["binding_terms_ready"]:
            raise ProductContractHold("catalogue terms result conflicts with canonical rules")
        blockers = original["readiness_blockers"]
        if (type(row.get("readiness_blockers")) is not list
                or row["readiness_blockers"] != blockers):
            raise ProductContractHold("catalogue per-SKU blocker ledger inconsistent")
        blocker_count.update(blockers)
        index[row["product_code"]] = row
    summary = catalogue.get("blocker_counts")
    if (not isinstance(summary, Mapping)
            or set(summary) != set(blocker_count)
            or any(type(x) is not int or x < 0 for x in summary.values())
            or dict(blocker_count) != dict(summary)):
        raise ProductContractHold("catalogue blocker totals inconsistent")
    specs = {spec.product_code: spec for spec in PREDICTIVE_REVENUE_PRODUCTS}
    if not set(specs).issubset(index):
        raise ProductContractHold("missing original founder-approved flagship SKU")
    for code, spec in specs.items():
        row = index[code]
        price = row.get("price_basis")
        if (not isinstance(price, Mapping)
                or price.get("state") != "VERIFIED"
                or type(price.get("amount_cents")) is not int
                or price["amount_cents"] != spec.deployment_price_cents
                or price.get("currency") != spec.currency):
            raise ProductContractHold("original flagship pricing conflicts with policy")
    projected: list[dict[str, Any]] = []
    for item in contracts["products"]:
        raw = index[item["product_code"]]
        blockers = list(raw["readiness_blockers"])
        ready = item["existing_catalogue_terms_flag_observed"]
        projected.append({
            **item,
            "original_catalogue_version": str(raw.get("version") or ""),
            "original_catalogue_active": raw["active"],
            "original_catalogue_readiness_blockers": blockers,
            "terms_policy_state": (
                "CATALOGUE_TERMS_FLAG_OBSERVED_EXTERNAL_ACCEPTANCE_UNVERIFIED"
                if ready else "CATALOGUE_TERMS_NOT_READY"
            ),
            "forecast_admission_status": "HELD_ORIGINAL_OUTCOME_AND_BASELINE_ABSENT",
            "product_deployment_status": "UNVERIFIED_SCOPE_AND_FULFILMENT",
            "first_owner_action": (
                "CATALOGUE_OWNER_CLEAR_ORIGINAL_BLOCKERS" if blockers
                else "TENANT_EVIDENCE_OWNER_VERIFY_CUSTOMER_AND_CONTRACT"
            ),
        })
    counts = Counter(row["product_family"] for row in projected)
    ready_counts = Counter(row["product_family"] for row in projected
                           if row["existing_catalogue_terms_flag_observed"])
    tiers = [
        {
            "product_code": row["product_code"],
            "approved_entry_price_cents": specs[row["product_code"]].deployment_price_cents,
            "currency": "USD",
            "capability_depth": row["tier_depth"],
            "original_catalogue_readiness_blockers":
                row["original_catalogue_readiness_blockers"],
            "customer_deployment_verified": False,
            "next_owner_action": row["first_owner_action"],
        }
        for row in projected if row["product_code"] in specs
    ]
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": "CANONICAL_CATALOGUE_POLICY_RECONCILED_SOURCE_DB_UNVERIFIED",
        "original_catalogue_generated_at_utc": source_time.isoformat(),
        "catalogue_age_seconds": int(max(age, 0)),
        "source_root_custody_verified": False,
        "source_original_db_receipt_authenticated": False,
        "catalogue_product_count": len(projected),
        "catalogue_active_count": catalogue["active_count"],
        "catalogue_terms_ready_count": contracts["existing_catalogue_terms_ready_count"],
        "family_product_counts": dict(sorted(counts.items())),
        "family_terms_flag_counts": dict(sorted(ready_counts.items())),
        "all_eight_known_product_families_covered": set(counts) == set(LANES),
        "original_catalogue_blocker_counts": dict(sorted(blocker_count.items())),
        "flagship_deployments": tiers,
        "products": projected,
        "tenant_customer_forecast_verified": False,
        "customer_entitlement_verified": False,
        "enterprise_delivery_verified": False,
        "recognized_revenue_changed": False,
        "actual_revenue_verified": False,
        "source_snapshot_mutated": False,
        "database_writes": False,
        "outbound_sent": False,
        "execution_authority": "none",
    }


def _read_bounded_file(path: Path, *, owner_uid: int) -> tuple[dict[str, Any], str, datetime]:
    """The file owner proves local filesystem custody, never DB provenance."""
    flags = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError:
        raise ProductContractHold("original local catalogue unavailable") from None
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        if (not stat.S_ISREG(before.st_mode) or before.st_uid != owner_uid
                or before.st_mode & 0o022
                or before.st_size <= 0 or before.st_size > MAX_SOURCE_BYTES):
            raise ProductContractHold("unsafe source file custody")
        raw = stream.read(MAX_SOURCE_BYTES + 1)
        after = os.fstat(stream.fileno())
        if (len(raw) != before.st_size or len(raw) > MAX_SOURCE_BYTES
                or before.st_ino != after.st_ino
                or before.st_mtime_ns != after.st_mtime_ns
                or before.st_size != after.st_size):
            raise ProductContractHold("source changed during single read")
    try:
        obj = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise ProductContractHold("original local catalogue invalid JSON") from None
    if not isinstance(obj, dict):
        raise ProductContractHold("original local catalogue not an object")
    timestamp = datetime.fromtimestamp(before.st_mtime, timezone.utc)
    return obj, sha256(raw).hexdigest(), timestamp


def review_existing_local_catalogue(*, as_of: datetime | None = None) -> dict[str, Any]:
    """One fixed, on-demand original source read; no privileged subprocesses."""
    now = as_of if as_of is not None else datetime.now(timezone.utc)
    doc, digest, mtime = _read_bounded_file(ROOT_CATALOGUE, owner_uid=0)
    result = _review_catalogue(doc, as_of=now)
    if abs((_stamp(doc["generated_at"]) - mtime).total_seconds()) > MAX_CLOCK_SKEW_SECONDS:
        raise ProductContractHold("source file time and generated_at drift")
    return {
        **result,
        "source_root_custody_verified": True,
        "local_snapshot_custody_status": CUSTODY_STATUS,
        "local_snapshot_sha256_for_change_detection_only": digest,
    }
