"""Read-only two-file website CTA release diff for ASTRA review."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from empire_os.earned_media_public_cta_release import review_public_cta_candidate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", action="store_true", required=True)
    parser.add_argument("--repo-root", type=Path,
                        default=Path(__file__).resolve().parents[1])
    parser.add_argument("--production-root", type=Path,
                        default=Path("/srv/empire_os"))
    parser.add_argument("--emit-patch", action="store_true",
                        help="Print exact two-file patch to stdout, not modify production")
    args = parser.parse_args(argv)
    packet = review_public_cta_candidate(
        args.repo_root, live_root=args.production_root,
        include_patch=args.emit_patch,
    )
    if args.emit_patch:
        if packet.get("source_patch"):
            sys.stdout.write(packet["source_patch"])
        else:
            print(json.dumps({"status": packet["status"],
                              "reason_code": packet.get("reason_code"),
                              "deployment_executed": False}, sort_keys=True),
                  file=sys.stderr)
    else:
        print(json.dumps(packet, sort_keys=True))
    return 0 if packet["status"] == (
        "EXACT_TWO_FILE_PUBLIC_CTA_CANDIDATE_OWNER_REVIEW_REQUIRED"
    ) else 2


if __name__ == "__main__":
    raise SystemExit(main())
