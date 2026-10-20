"""Read-only orchestration handoff, no fake OpenManus agent or dispatch."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from empire_os.inbound_manus_review_bridge import OfflineManusReviewOutbox


def main() -> None:
    p = argparse.ArgumentParser(description="OpenManus review-job staging; NEVER executes a worker")
    p.add_argument("--outbox", required=True, type=Path)
    p.add_argument("--code-commit")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--read-only", action="store_true")
    mode.add_argument("--stage-offline-only", action="store_true")
    args = p.parse_args()
    try:
        if args.stage_offline_only:
            if not args.code_commit:
                raise ValueError("full_reviewed_code_commit_required")
            with OfflineManusReviewOutbox(args.outbox) as outbox:
                job, created = outbox.stage(
                    code_commit=args.code_commit, at=datetime.now(timezone.utc),
                )
                result = {"job": job.job_id, "created": created, **outbox.summary()}
        else:
            with OfflineManusReviewOutbox(args.outbox, read_only=True) as outbox:
                result = outbox.summary()
    except Exception as exc:
        p.error(f"manus_handoff_denied: {type(exc).__name__}")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
