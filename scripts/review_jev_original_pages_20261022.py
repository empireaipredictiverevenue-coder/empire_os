"""Build PRIVATE real GSC URL candidate queue for human Jev SEO evaluation.

Reuses the existing first-party page-only 404 review. Never writes ground-truth
labels or calls Jev. A pending case is not a labelled evaluation case.
"""
from __future__ import annotations

import argparse
from datetime import date
import fcntl
import json
import os
from pathlib import Path

from empire_os.search_intelligence.jev_evidence_intake import (
    JevEvidenceIntakeHeld, build_original_page_review_intake,
    intake_summary_only,
)
from scripts.review_live_search_page_404_revenue_readonly import run as existing_run

BASE = Path("/home/ubuntu/empire_releases/search_jev_owner_receipts_20261021")
OUT = BASE / "jev_original_page_review_intake_20261022.json"
START, END = date(2026, 10, 7), date(2026, 10, 19)


def review(*, write_private: bool = False) -> dict[str, object]:
    if write_private:
        if BASE.is_symlink() or not BASE.is_dir() or BASE.stat().st_mode & 0o077:
            raise JevEvidenceIntakeHeld("PRIVATE_BASE_UNSAFE")
        if OUT.exists() or OUT.is_symlink():
            raise JevEvidenceIntakeHeld("SOURCE_INTAKE_ALREADY_EXISTS_NO_OVERWRITE")
    report = existing_run(start=START, end=END)
    intake = build_original_page_review_intake(report)
    summary = intake_summary_only(intake)
    if not write_private:
        return {**summary, "private_receipt_written": False, "gsc_network_read_only": True}
    # Never use a writable file already at the destination, including symlinks.
    fd = os.open(str(OUT), os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(intake, stream, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        OUT.unlink(missing_ok=True)
        raise
    return {**summary, "private_receipt_written": True,
            "private_receipt_path": str(OUT), "gsc_network_read_only": True}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-private", action="store_true",
                        help="Create a 0600 one-time intake in existing private evidence directory")
    args = parser.parse_args()
    try:
        # Single process lock, never launch parallel GSC/HTTP reviews.
        if args.write_private:
            fd = os.open(str(BASE / ".original-page-intake.lock"),
                         os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "r+") as lockfile:
                fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
                print(json.dumps(review(write_private=True), sort_keys=True))
        else:
            print(json.dumps(review(), sort_keys=True))
    except (JevEvidenceIntakeHeld, OSError) as exc:
        print(json.dumps({
            "status": "ORIGINAL_PAGE_INTAKE_HELD",
            "reason": str(exc) if isinstance(exc, JevEvidenceIntakeHeld)
                      else "SOURCE_OR_RECEIPT_UNAVAILABLE",
            "accepted_human_ground_truth_labels": 0,
            "automatic_jev_inference": False,
            "publication_authorized": False,
            "execution_authority": "NONE",
        }, sort_keys=True))
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
