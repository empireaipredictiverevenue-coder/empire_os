#!/usr/bin/env python3
"""Private calibrated evidence ranking + source-specific page outcomes (no release)."""
from __future__ import annotations

import argparse
from pathlib import Path
import json
import sys

from empire_os.microsite_ranked_production_queue_v4 import build_ranked_microsite_queue
from empire_os.microsite_calibration_bridge_v4 import review_historical_model_calibration
from empire_os.microsite_page_outcomes_v4 import (
    read_original_weekly_search_report, build_microsite_outcome_register,
)
from empire_os.microsite_commercial_intelligence_v3 import build_microsite_commercial_review
from empire_os.microsite_verified_outcomes_v5 import (
    OriginalPageReaders, build_approved_microsite_scorecard,
)

DEFAULT_ORIGINAL_WEEKLY = Path(
    "/home/ubuntu/empire_releases/seo_weekly_gsc_two_page_20261022/"
    "weekly_two_page_2026-10-26.json"
)
ORIGINAL_WEEKLY_ROOT = DEFAULT_ORIGINAL_WEEKLY.parent


def run(
    *, candidate_source: Path, commercial_source: Path,
    output: Path, gsc_source: Path | None = None,
    weekly_source: Path | None = DEFAULT_ORIGINAL_WEEKLY,
) -> dict:
    out = output.expanduser().resolve()
    if (out == Path("/srv/empire_os")
            or Path("/srv/empire_os") in out.parents
            or out == Path("/var/www") or Path("/var/www") in out.parents):
        raise ValueError("no writes to production")
    if candidate_source.is_symlink() or commercial_source.is_symlink():
        raise ValueError("symlink source not allowed")
    data = json.loads(candidate_source.read_text(encoding="utf-8"))
    specs = data.get("candidates") if isinstance(data, dict) and "candidates" in data else [data]
    commercial = json.loads(commercial_source.read_text(encoding="utf-8"))
    gsc = None
    if gsc_source:
        if gsc_source.is_symlink():
            raise ValueError("GSC bridge symlink not allowed")
        gsc = json.loads(gsc_source.read_text(encoding="utf-8"))
    # The trusted owner has not supplied later outcome receipts for the model.
    # Reuse the original calibration reviewer rather than invent a pass.
    calibration = review_historical_model_calibration([])
    queue = build_ranked_microsite_queue(
        specs, commercial=commercial, gsc=gsc, calibration=calibration)
    if weekly_source is not None:
        path = weekly_source.expanduser().absolute()
        if path.parent != ORIGINAL_WEEKLY_ROOT:
            raise ValueError("weekly GSC report is not in original owner source")
        baseline = read_original_weekly_search_report(path)
    else:
        baseline = None
    outcomes = build_microsite_outcome_register(queue, original_weekly_gsc=baseline)
    # No original owner reader authorises a newly minted factory route yet.
    # Scorecard reports every factory page's metrics as unknown, not zero.
    verified = None
    if baseline is not None:
        window = baseline["current_window"]
        verified = build_approved_microsite_scorecard(
            specs, readers=OriginalPageReaders(),
            window_start=window["start_date"], window_end=window["end_date"])
    out.mkdir(parents=True, exist_ok=True)
    for name, payload in (
        ("ranked_research_queue.json", queue),
        ("microsite_outcomes.json", outcomes),
        ("calibration_readiness.json", calibration),
    ):
        (out / name).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8")
    if verified is not None:
        (out / "approved_page_measurement_readiness_v5.json").write_text(
            json.dumps(verified, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8")
    return {
        "status": "PRIVATE_RANKED_RESEARCH_QUEUE",
        "candidates_ranked": queue["candidate_count"],
        "calibrated_models": calibration["verified_model_count"],
        "publishable_candidates": queue["publishable_count"],
        "approved_factory_pages": 0,
        "commercial_outcome_attribution_verified": False,
        "approved_page_measurement_v5_written": verified is not None,
        "external_model_calls": 0,
        "new_services": 0,
        "production_changed": False,
        "output": str(out),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-source", required=True, type=Path)
    parser.add_argument("--commercial-source", required=True, type=Path)
    parser.add_argument("--gsc-bridge", type=Path)
    parser.add_argument("--weekly-gsc", type=Path, default=DEFAULT_ORIGINAL_WEEKLY)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(run(
            candidate_source=args.candidate_source,
            commercial_source=args.commercial_source,
            output=args.output,
            gsc_source=args.gsc_bridge,
            weekly_source=args.weekly_gsc,
        ), sort_keys=True))
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(f"microsite V4 source review error: {exc}", file=sys.stderr)
        sys.exit(2)
