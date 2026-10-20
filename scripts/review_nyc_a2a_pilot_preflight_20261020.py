#!/usr/bin/env python3
"""Read existing NYC evidence; produce an internal, rights-held B2B pilot gate."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

from empire_os.a2a_nyc_commercial_evidence_gate import inspect_nyc_pilot
from empire_os.a2a_data_campaign_release_review import assess_campaign_readiness

REPORTS = Path("/srv/empire_os/runtime/data_brokerage")
GPS = Path("/srv/empire_os/runtime/market_sweeps/revenue_gps_latest.json")
OUTPUT = Path(__file__).resolve().parents[1] / "runtime" / "a2a_commercial_signal_mining" / "nyc_commercial_preflight.json"

FILES = {
    "report": REPORTS / "nyc_dobnow_property_three_agency_latest.json",
    "provenance": REPORTS / "nyc_dobnow_property_three_agency_latest.provenance.json",
    "catalogue": REPORTS / "internal_product_catalog_latest.json",
    "revenue_gps": GPS,
}


def _read(path: Path, *, size: int = 1_000_000) -> tuple[dict, bytes]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > size:
        raise ValueError("missing_unsafe_or_oversized_source: " + path.name)
    raw = path.read_bytes()
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise ValueError("source_root_must_be_object: " + path.name)
    return obj, raw


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="NYC A2A data-product preflight (observe-only)")
    p.add_argument("--source-root", type=Path, default=REPORTS)
    p.add_argument("--gps-file", type=Path, default=GPS)
    p.add_argument("--review-campaigns", action="store_true", help="Bind commercial proof to existing A2A campaign drafts")
    p.add_argument("--write-local", action="store_true")
    args = p.parse_args(argv)
    root = args.source_root
    files = {
        "report": root / "nyc_dobnow_property_three_agency_latest.json",
        "provenance": root / "nyc_dobnow_property_three_agency_latest.provenance.json",
        "catalogue": root / "internal_product_catalog_latest.json",
        "revenue_gps": args.gps_file,
    }
    inputs = {k: _read(v) for k, v in files.items()}
    result = inspect_nyc_pilot(
        report=inputs["report"][0],
        report_sha256=hashlib.sha256(inputs["report"][1]).hexdigest(),
        provenance=inputs["provenance"][0],
        catalogue=inputs["catalogue"][0],
        revenue_gps=inputs["revenue_gps"][0],
    )
    if args.review_campaigns:
        campaign_path = OUTPUT.parent / "data_campaign_experiments.json"
        campaigns = _read(campaign_path)[0]
        release_review = assess_campaign_readiness(campaigns, result)
        result["campaign_release_review"] = release_review
    if args.write_local:
        path = OUTPUT
        if path.parent.is_symlink():
            raise ValueError("unsafe_output_directory")
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise ValueError("unsafe_report_target")
        fd, tmp = tempfile.mkstemp(prefix=".nyc_evidence_", dir=path.parent, text=True)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf8") as f:
                json.dump(result, f, indent=2, sort_keys=True)
                f.write("\n")
            os.replace(tmp, path)
            if args.review_campaigns:
                other = OUTPUT.parent / "data_campaign_release_review.json"
                if other.is_symlink() or (other.exists() and not other.is_file()):
                    raise ValueError("unsafe_release_review_target")
                fd2, temp2 = tempfile.mkstemp(prefix=".campaign_preflight_", dir=other.parent, text=True)
                try:
                    os.fchmod(fd2, 0o600)
                    with os.fdopen(fd2, "w", encoding="utf8") as f2:
                        json.dump(release_review, f2, indent=2, sort_keys=True)
                        f2.write("\n")
                    os.replace(temp2, other)
                finally:
                    if os.path.exists(temp2):
                        os.unlink(temp2)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
