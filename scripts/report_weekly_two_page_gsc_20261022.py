"""One-shot, read-only GSC observer for the two published SEO improvements.

Default shows JSON but stores nothing. --write-private stores ONE immutable
weekly receipt per as-of date in an owner-only directory. Used by a bounded
systemd timer if explicitly enabled; never performs Jev calls or outreach.
"""
from __future__ import annotations

import argparse
from datetime import date, timezone, datetime
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path

from empire_os.search_intelligence.weekly_two_page_outcomes import build_weekly_report
from scripts.review_live_gsc_page_performance import local_gsc_get

ROOT = Path("/home/ubuntu/empire_releases/seo_weekly_gsc_two_page_20261022")


def run(*, as_of: date, write_private: bool) -> dict:
    report = build_weekly_report(as_of=as_of, get_json=local_gsc_get)
    if not write_private:
        return report
    ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    if ROOT.is_symlink() or ROOT.stat().st_mode & 0o077 or ROOT.stat().st_uid != os.geteuid():
        raise ValueError("PRIVATE_REPORT_DIR_UNSAFE")
    lock_file=ROOT/".week-observer.lock"
    lock_fd=os.open(lock_file, os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    with os.fdopen(lock_fd,"rb") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        target=ROOT/f"weekly_two_page_{as_of.isoformat()}.json"
        if target.exists() or target.is_symlink():
            raise ValueError("WEEKLY_REPORT_ALREADY_CREATED_NO_OVERWRITE")
        fd=os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,"w",encoding="utf-8") as f:
            json.dump(report,f,sort_keys=True,indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
    return {
        "status":"PRIVATE_WEEKLY_GSC_REPORT_WRITTEN",
        "as_of":as_of.isoformat(),
        "receipt_sha256":sha256(target.read_bytes()).hexdigest(),
        "private_receipt":str(target),
        "source_errors":report["source_errors"],
        "previous_window":report["previous_window"]["source_status"],
        "current_window":report["current_window"]["source_status"],
        "comparison_valid_after_release":report["comparison_valid_after_release"],
        "website_mutations":False,
        "execution_authority":"NONE",
    }


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--as-of",type=date.fromisoformat,
                        default=datetime.now(timezone.utc).date())
    parser.add_argument("--write-private",action="store_true")
    args=parser.parse_args()
    try:
        print(json.dumps(run(as_of=args.as_of,write_private=args.write_private),sort_keys=True))
    except (OSError,ValueError,TypeError) as exc:
        print(json.dumps({"status":"WEEKLY_GSC_REPORT_HELD",
          "reason":str(exc) if isinstance(exc,ValueError) else "SOURCE_UNAVAILABLE",
          "website_mutations":False,"execution_authority":"NONE"},sort_keys=True))
        raise SystemExit(2) from None


if __name__=="__main__":
    main()
