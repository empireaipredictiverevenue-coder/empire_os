"""Prepare a PRIVATE Empire AI Data Brokerage product evidence catalogue.

Reads a protected *existing* canonical V16 custody inspector report from stdin
(and existing local Permit/Common Crawl intelligence). Prints safe aggregate
summary, optionally materializes one local 0600 internal review packet.
No source HTTP, paid API, DB write, external email, asset modification or sale.

Usage (on canonical production Ubuntu, with existing protected read only):
  sudo -n ./.venv/bin/python -B -m scripts.inspect_data_exchange_v16_live \
    --read-only --rights-docket |
  ./.venv/bin/python -B -m scripts.preview_data_brokerage_products \
    --read-only --inspection-stdin --materialize-private
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO
import argparse
import fcntl
import json
import os
import sys

from empire_os.data_brokerage_product_catalog import (
    build_data_brokerage_product_catalog, validate_internal_brokerage_catalog,
)
from empire_os.permit_project_intelligence import analyze_permit_project_intelligence
from empire_os.free_dataset_intelligence import inspect_free_commoncrawl_dataset
from empire_os.founder_asset_provenance import build_founder_asset_receipt

CANONICAL_ROOT = Path("/srv/empire_os")
PRIVATE_REPORT = Path("runtime/data_brokerage/internal_product_catalog_latest.json")
LOCK = Path("runtime/data_brokerage/.catalog_preview.lock")
ASSET_MANIFEST_DIR = Path("runtime/media/provenance")
MAX_INSPECTOR_STDIN = 256 * 1024


def _inspection(inp: TextIO) -> dict[str, Any]:
    raw = inp.read(MAX_INSPECTOR_STDIN + 1)
    if len(raw) > MAX_INSPECTOR_STDIN:
        raise ValueError("protected_inspection_too_large")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("protected_inspection_not_dict")
    return payload


def _write_review(root: Path, result: dict[str, Any]) -> None:
    if root.resolve() != CANONICAL_ROOT:
        raise ValueError("no_materialization_outside_canonical_worktree")
    if not validate_internal_brokerage_catalog(result):
        raise ValueError("catalog_rights_or_integrity_failed")
    path = root / PRIVATE_REPORT
    lock = root / LOCK
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.touch(exist_ok=True)
    os.chmod(lock, 0o600)
    with lock.open("r+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        temp = path.with_name(path.name + f".tmp.{os.getpid()}")
        try:
            with temp.open("x", encoding="utf8") as target:
                os.chmod(temp, 0o600)
                json.dump(result, target, sort_keys=True, indent=2, allow_nan=False)
                target.write("\n")
            temp.replace(path)
        finally:
            if temp.exists():
                temp.unlink()
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _write_founder_receipt(root: Path, receipt: dict[str, Any]) -> None:
    """Private, owner-asserted asset hash; never copy or transform image bytes."""
    if root.resolve() != CANONICAL_ROOT:
        raise ValueError("noncanonical_asset_registration_blocked")
    path = root / ASSET_MANIFEST_DIR / (receipt["asset_id"] + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise ValueError("existing_asset_receipt_unreadable") from None
        if existing != receipt:
            raise ValueError("existing_asset_receipt_immutable_use_new_version_id")
        return
    temp = path.with_name(path.name + f".tmp.{os.getpid()}")
    try:
        with temp.open("x", encoding="utf8") as target:
            os.chmod(temp, 0o600)
            json.dump(receipt, target, indent=2, sort_keys=True, allow_nan=False)
            target.write('\n')
        temp.replace(path)
    finally:
        if temp.exists():
            temp.unlink()


def main(argv: list[str] | None = None, *,
         stdin: TextIO | None = None,
         repo_root: Path = CANONICAL_ROOT) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--read-only", action="store_true")
    p.add_argument("--inspection-stdin", action="store_true")
    p.add_argument("--materialize-private", action="store_true")
    p.add_argument("--founder-asset-file", type=Path, default=None)
    p.add_argument("--founder-asset-id", default=None)
    p.add_argument("--founder-origin",
                   choices=("FOUNDER_ORIGINAL","FOUNDER_DIRECTED_AI_ASSISTED"))
    p.add_argument("--founder-ai-assistance",
                   choices=("NONE_DECLARED","AI_ASSISTED_DECLARED","UNKNOWN"))
    p.add_argument("--founder-ownership-declared", action="store_true")
    args = p.parse_args(argv)
    report: dict[str, Any]
    try:
        if not args.read_only:
            raise ValueError("explicit_read_only_required")
        if args.materialize_private and not args.inspection_stdin:
            raise ValueError("protected_inspection_required_for_catalog_materialization")
        root = Path(repo_root).resolve()
        if root != CANONICAL_ROOT:
            if args.materialize_private:
                raise ValueError("canonical_repo_required")
        source = _inspection(stdin if stdin is not None else sys.stdin) if (
            args.inspection_stdin) else None
        founder_asset = None
        if args.founder_asset_file is not None:
            if not (args.founder_ownership_declared
                    and args.founder_asset_id
                    and args.founder_origin
                    and args.founder_ai_assistance):
                raise ValueError("asset_attestation_fields_missing")
            founder_asset = build_founder_asset_receipt(
                args.founder_asset_file,
                asset_id=args.founder_asset_id,
                origin_class=args.founder_origin,
                ai_assistance=args.founder_ai_assistance,
                founder_ownership_declared=True,
                third_party_components_declared=None,
            )
        elif any((args.founder_asset_id, args.founder_origin,
                  args.founder_ai_assistance, args.founder_ownership_declared)):
            raise ValueError("founder_asset_file_missing")
        catalog = build_data_brokerage_product_catalog(
            assessed_at=datetime.now(timezone.utc),
            exchange_inspection=source,
            permit_intelligence=analyze_permit_project_intelligence(root),
            graph_intelligence=(
                inspect_free_commoncrawl_dataset()
                if root == CANONICAL_ROOT else None
            ),
            founder_asset_receipt=founder_asset,
        )
        if not validate_internal_brokerage_catalog(catalog):
            raise ValueError("catalog_internal_preflight_failed")
        if args.materialize_private:
            if catalog["products"][0]["source_evidence_summary"]["status"] != (
                "CANONICAL_CUSTODY_OBSERVED_RELEASE_HELD"
            ):
                raise ValueError("protected_custody_readback_required")
            _write_review(root, catalog)
            if founder_asset is not None:
                _write_founder_receipt(root, founder_asset)
        report = {
            "status": "PRIVATE_INTERNAL_BROKERAGE_REVIEW_READY",
            "mode": "OBSERVE",
            "schema_version": catalog["schema_version"],
            "product_count": catalog["product_count"],
            "product_ids": [r["product_id"] for r in catalog["products"]],
            "source_custody_state": catalog["products"][0][
                "source_evidence_summary"]["status"],
            "licensed_third_party_resale_authorized": False,
            "founder_owned_assets_registered": catalog[
                "registered_founder_owned_asset_count"],
            "founder_asset_integrity_sha256": (
                founder_asset["file_sha256"] if founder_asset is not None else None
            ),
            "founder_origin_independently_verified": False,
            "watermark_removal_attempted": False,
            "preview_materialized_private": bool(args.materialize_private),
            "private_review_ref": (
                str(PRIVATE_REPORT) if args.materialize_private else None),
            "scope_sha256": catalog["evidence_scope_sha256"],
            "paid_api_calls": 0,
            "database_writes": False,
            "customer_delivery_enabled": False,
            "outbound_sent": False,
            "execution_authority": "none",
        }
    except (OSError, ValueError, TypeError, KeyError, UnicodeError) as exc:
        report = {
            "status": "HOLD",
            "reason_code": type(exc).__name__,
            "preview_materialized_private": False,
            "database_writes": False,
            "customer_delivery_enabled": False,
            "execution_authority": "none",
        }
    print(json.dumps(report, sort_keys=True, allow_nan=False))
    return 0 if report["status"] == "PRIVATE_INTERNAL_BROKERAGE_REVIEW_READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
