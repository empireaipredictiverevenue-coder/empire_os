#!/usr/bin/env python3
"""Build private microsite research previews and optional first-party/local QA."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any

from empire_os.predictive_microsite_factory import build_candidate, review_portfolio
from empire_os.microsite_first_party_gsc_bridge import (
    connect_factory_to_gsc, read_existing_weekly_receipt,
)
from empire_os.microsite_local_copy_adapter import generate_local_copy_revision
from empire_os.microsite_commercial_intelligence_v3 import (
    read_original_buyer_snapshot, read_original_predictive_registry,
    build_microsite_commercial_review,
)

EXISTING_GSC_DIR = Path("/home/ubuntu/empire_releases/seo_weekly_gsc_two_page_20261022")
ORIGINAL_BUYER_COVERAGE = Path("/srv/empire_os/runtime/revenue/lead_smart/coverage/latest.json")


def _out_location(out_dir: Path) -> Path:
    resolved = out_dir.expanduser().resolve()
    # Write stage outputs outside production and release directories, never serve them.
    protected = (Path("/srv/empire_os"), Path("/var/www"), Path("/srv/empire_public"))
    if any(resolved == p or p in resolved.parents for p in protected):
        raise ValueError("refusing to write draft previews inside live runtime or site directories")
    return resolved


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8")


def run(
    source: Path, out_dir: Path,
    *,
    gsc_receipt: Path | None = None,
    local_rewrite_first: bool = False,
    observe_original_buyer_coverage: bool = False,
    read_original_forecast_registry: bool = False,
    forecast_reader=None,
) -> dict:
    raw = json.loads(source.read_text(encoding="utf-8"))
    specs = raw.get("candidates") if isinstance(raw, dict) and "candidates" in raw else [raw]
    if not isinstance(specs, list) or not 1 <= len(specs) <= 25:
        raise ValueError("input must contain 1-25 candidate proposals")
    if not all(isinstance(spec, dict) for spec in specs):
        raise ValueError("each candidate must be an object")

    resolved = _out_location(out_dir)
    # Complete input validation before any outputs are written.
    reviews = review_portfolio(specs)
    pages = [build_candidate(spec)[1] for spec in specs]
    bridge = None
    if gsc_receipt is not None:
        trusted_path = gsc_receipt.expanduser().absolute()
        if trusted_path.is_symlink() or trusted_path.parent != EXISTING_GSC_DIR:
            raise ValueError("GSC bridge only accepts original SEO-owned weekly source directory")
        receipt, receipt_hash = read_existing_weekly_receipt(trusted_path)
        bridge = connect_factory_to_gsc(specs, receipt, receipt_sha256=receipt_hash)

    original_snapshot = None
    snapshot_digest = None
    if observe_original_buyer_coverage:
        original_snapshot, snapshot_digest = read_original_buyer_snapshot(ORIGINAL_BUYER_COVERAGE)
    forecasts = None
    if read_original_forecast_registry:
        dsn = os.environ.get("EMPIRE_PREDICTIVE_REGISTRY_DSN", "")
        forecasts = read_original_predictive_registry(
            dsn, limit=100, reader=forecast_reader)
    commercial = build_microsite_commercial_review(
        specs, buyer_snapshot=original_snapshot,
        buyer_snapshot_sha256=snapshot_digest,
        forecast_rows=forecasts, now=datetime.now(timezone.utc),
    )

    rewrite = None
    if local_rewrite_first:
        try:
            rewrite = generate_local_copy_revision(specs[0])
        except (ValueError, OSError, TimeoutError) as exc:
            rewrite = {
                "schema_version": "empire.microsite_local_copy_draft.v1",
                "status": "HOLD_LOCAL_MODEL_UNAVAILABLE",
                "error_type": type(exc).__name__,
                "publication_authorized": False,
                "database_writes": False,
                "external_model_calls": 0,
            }

    resolved.mkdir(parents=True, exist_ok=True)
    for spec, packet, html in zip(specs, reviews, pages):
        ident = packet["id"]
        (resolved / f"{ident}.preview.html").write_text(html, encoding="utf-8")
        brief = [
            f"Candidate: {ident}",
            f"Territory: {packet['market']['area']}",
            f"Keyword: {packet['keyword']['record']['keyword']}",
            f"Audience: {packet['audience']}",
            f"Offer: {packet['offer']}",
            f"SlopMonster score: {packet['copy_audit']['score']}/5",
            f"Copy findings: {json.dumps(packet['copy_audit']['categories'], ensure_ascii=False)}",
            "Rewrite instruction: preserve the location, every source fact, technical limitations,",
            "source references, brand tone and the intent. Remove unsupported claims and vague phrasing.",
            "Never claim verified buyers, lead volume, calls, financial outcomes, or service capacity.",
            "Visual direction: accessible responsive premium dark-navy pages with gold and electric-blue accents.",
            "Use real browser screenshot testing before any owner-approved release.",
            "No external model invocation was performed by this script.",
        ]
        (resolved / f"{ident}.copy-design-brief.txt").write_text(
            "\n".join(brief) + "\n", encoding="utf-8")

    manifest = {
        "schema_version": "empire.microsite_factory_draft_batch.v2",
        "stage_only": True, "published": False, "execution_authority": "none",
        "candidates_reviewed": len(reviews),
        "held": sum(p["status"] == "HOLD_EVIDENCE" for p in reviews),
        "draft_review": sum(p["status"] == "DRAFT_REVIEW" for p in reviews),
        "previews": [p["id"] + ".preview.html" for p in reviews],
        "gsc_receipt_used": bridge is not None,
        "local_copy_revision_attempted": local_rewrite_first,
        "commercial_research_attached": True,
        "observed_original_buyer_coverage": observe_original_buyer_coverage,
        "original_predictive_registry_read": read_original_forecast_registry,
        "verified_forecast_records": commercial["candidates_with_valid_forecast_records"],
        "publishable_candidates": commercial["publishable_candidates"],
        "packets": reviews,
    }
    _write_json(resolved / "manifest.json", manifest)
    _write_json(resolved / "commercial_research_review.json", commercial)
    if bridge is not None:
        _write_json(resolved / "gsc_evidence_bridge.json", bridge)
    if rewrite is not None:
        _write_json(resolved / "local_copy_revision_review.json", rewrite)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--gsc-receipt", type=Path)
    parser.add_argument("--local-rewrite-first", action="store_true")
    parser.add_argument("--observe-original-buyer-coverage", action="store_true")
    parser.add_argument("--read-original-forecast-registry", action="store_true")
    args = parser.parse_args()
    try:
        result = run(args.input, args.output_dir,
                     gsc_receipt=args.gsc_receipt, local_rewrite_first=args.local_rewrite_first,
                     observe_original_buyer_coverage=args.observe_original_buyer_coverage,
                     read_original_forecast_registry=args.read_original_forecast_registry)
        print(json.dumps({
            key: result[key] for key in
            ("schema_version", "candidates_reviewed", "held", "draft_review",
             "stage_only", "published", "gsc_receipt_used",
             "local_copy_revision_attempted", "observed_original_buyer_coverage",
             "original_predictive_registry_read", "verified_forecast_records",
             "publishable_candidates", "previews")},
            sort_keys=True))
    except (OSError, RuntimeError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(f"microsite preview error: {exc}", file=sys.stderr)
        sys.exit(2)
