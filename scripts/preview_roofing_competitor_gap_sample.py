"""Prepare an original, source-checked $199 commercial roofing sample for Founder.

Usage:
  cd /srv/empire_os
  ./.venv/bin/python -B -m scripts.preview_roofing_competitor_gap_sample --read-only
  ./.venv/bin/python -B -m scripts.preview_roofing_competitor_gap_sample --read-only --write-private

This emits a private OBSERVE-only Markdown report and SHA receipt, not a
customer order, website publication, paid service or any outbound mail.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import argparse
import fcntl
import json
import os
import stat

from empire_os.data_brokerage_roofing_sample import (
    build_roofing_competitor_sample, render_roofing_sample_markdown,
)

ROOT = Path("/srv/empire_os")
REPORT = Path("runtime/data_brokerage/roofing_competitor_gap_sample_20261018.md")
RECEIPT = Path("runtime/data_brokerage/roofing_competitor_gap_sample_20261018.provenance.json")
LOCK = Path("runtime/data_brokerage/.roofing_competitor_sample.lock")
RECEIPT_SCHEMA = "empire.data_brokerage.roofing_sample_receipt.v1"


def _write_once(path: Path, data: bytes) -> str:
    if path.is_symlink():
        raise ValueError("private_report_symlink_not_allowed")
    target_hash = sha256(data).hexdigest()
    if path.exists():
        if (path.read_bytes() != data
                or stat.S_IMODE(path.stat().st_mode) != 0o600):
            raise ValueError("existing_private_report_differs_use_versioned_release")
        return target_hash
    temp = path.with_name(path.name + f".tmp.{os.getpid()}")
    try:
        with temp.open("xb") as stream:
            os.chmod(temp, 0o600)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        temp.replace(path)
    finally:
        if temp.exists():
            temp.unlink()
    return target_hash


def write_private_report(root: Path, *, report: dict, markdown: str) -> dict:
    if root.resolve() != ROOT:
        raise ValueError("canonical_runtime_required")
    if (report.get("customer_delivery_authorized") is not False
            or report.get("outbound_sent") is not False
            or report.get("raw_dataset_resale_authorized") is not False
            or report.get("received_payment_verified") is not False
            or report.get("paid_api_calls") != 0):
        raise ValueError("not_an_approved_private_review")
    target = root / REPORT
    receipt_path = root / RECEIPT
    lock_path = root / LOCK
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    if lock_path.is_symlink():
        raise ValueError("private_lock_symlink_not_allowed")
    if not lock_path.exists():
        lock_path.touch(mode=0o600, exist_ok=False)
    os.chmod(lock_path, 0o600)
    body = markdown.encode("utf8")
    provenance = {
        "schema_version": RECEIPT_SCHEMA,
        "asset_class": "FOUNDER_REVIEW_AI_ASSISTED_ORIGINAL_RESEARCH_DRAFT",
        "origin_method": "Empire_AI_analysis_using_previously_downloaded_free_source_evidence",
        "ai_assistance_disclosed": True,
        "founder_independent_ownership_proven": False,
        "c2pa_signature_issued": False,
        "report_sha256": sha256(body).hexdigest(),
        "source_evidence_sha256": report["internal_evidence_sha256"],
        "reviewed_graph_sha256": report["source"]["source_review_sha256"],
        "candidate_rows_sha256": report["source"]["candidate_rows_sha256"],
        "raw_dataset_resale_authorized": False,
        "customer_delivery_authorized": False,
        "outbound_sent": False,
        "paid_api_calls": 0,
        "empiredb_writes": False,
        "execution_authority": "none",
    }
    receipt_bytes = (
        json.dumps(provenance, sort_keys=True, indent=2) + "\n"
    ).encode("utf8")
    with lock_path.open("r+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        # Prevent an existing receipt for a different analysis from being
        # paired with a new report, even on repeated commands.
        if receipt_path.exists():
            if receipt_path.read_bytes() != receipt_bytes:
                raise ValueError("existing_source_receipt_differs")
        if target.exists() and target.read_bytes() != body:
            raise ValueError("existing_original_report_differs")
        _write_once(target, body)
        _write_once(receipt_path, receipt_bytes)
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    return provenance


def main(argv: list[str] | None = None, *, root: Path = ROOT) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", action="store_true")
    parser.add_argument("--write-private", action="store_true")
    args = parser.parse_args(argv)
    try:
        if not args.read_only:
            raise ValueError("explicit_read_only_required")
        sample = build_roofing_competitor_sample()
        markdown = render_roofing_sample_markdown(sample)
        receipt = (
            write_private_report(root, report=sample, markdown=markdown)
            if args.write_private else None
        )
        print(json.dumps({
            "status": "FOUNDER_REVIEW_SAMPLE_PREPARED",
            "mode": "OBSERVE",
            "product_code": "competitor_search_gap",
            "approved_price_usd": sample["approved_list_price_usd"],
            "historical_graph_association_counts": {
                k:sample["comparison"][k] for k in (
                    "nations_source_domain_count","tecta_source_domain_count",
                    "shared_source_domain_count","nations_only_count",
                    "tecta_only_count","union_source_domain_count",
                )
            },
            "source_evidence_sha256": sample["internal_evidence_sha256"],
            "report_sha256": sha256(markdown.encode("utf8")).hexdigest(),
            "private_report_materialized": bool(receipt),
            "private_report_ref": str(REPORT) if receipt else None,
            "private_receipt_ref": str(RECEIPT) if receipt else None,
            "live_backlinks_verified": 0,
            "buyer_or_payment_verified": False,
            "raw_third_party_resale_authorized": False,
            "outbound_sent": False,
            "paid_api_calls": 0,
            "empiredb_writes": False,
            "execution_authority": "none",
        }, sort_keys=True))
        return 0
    except (OSError, TypeError, KeyError, ValueError) as exc:
        print(json.dumps({
            "status": "HOLD",
            "reason_code": type(exc).__name__,
            "report_written": False,
            "outbound_sent": False,
            "paid_api_calls": 0,
            "execution_authority": "none",
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
