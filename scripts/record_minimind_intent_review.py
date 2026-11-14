#!/usr/bin/env python3
"""Record an explicitly human-reviewed MiniMind intent label, offline only.

Operates only on the existing private EmpireOS review archive. Never runs
from the community-intent timer and never creates labels from weak predictions.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from empire_os.minimind_intent_shadow import (
    ALLOWED_CLASSES, manifest_from_review_archive, merge_review_archive,
)

ROOT = Path("/srv/empire_os")
ARCHIVE = Path("runtime/community_intent/minimind_shadow/review_archive_latest.json")
LABELS = Path("runtime/community_intent/minimind_shadow/manual_adjudications.json")
SCHEMA = "empire.minimind_manual_adjudications.v1"
MAX_FILE_BYTES = 2_500_000


def _read_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("unsafe or missing source file")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("expected JSON object")
    return data


def record_review(
    *,
    root: Path,
    sample_ref: str,
    input_digest: str,
    label: str,
    reviewer_ref: str,
    review_note: str,
    source_url: str,
    explicitly_reviewed: bool,
    reviewed_at: datetime,
) -> dict:
    """Write one local human attestation; no network, training or promotion."""
    if explicitly_reviewed is not True:
        raise ValueError("explicit source review confirmation required")
    if not reviewer_ref or not reviewer_ref.strip() or len(reviewer_ref) > 120:
        raise ValueError("named reviewer reference required")
    if not review_note or not review_note.strip() or len(review_note) > 1000:
        raise ValueError("review rationale required")
    if label not in ALLOWED_CLASSES:
        raise ValueError("unsupported intent classification")
    if reviewed_at.tzinfo is None or reviewed_at.utcoffset() is None:
        raise ValueError("review timestamp must include timezone")
    now = datetime.now(timezone.utc)
    if reviewed_at > now or (now - reviewed_at).total_seconds() > 86400:
        raise ValueError("review timestamp must be current")
    root = root.resolve()
    archive_path = root / ARCHIVE
    label_path = root / LABELS
    if label_path.parent.is_symlink() or label_path.is_symlink():
        raise ValueError("unsafe label destination")
    label_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock_path = label_path.parent / ".minimind_shadow.lock"
    if lock_path.is_symlink():
        raise ValueError("unsafe review lock path")
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(fd, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        archive = _read_json(archive_path)
        manifest_from_review_archive(archive)
        merge_review_archive(archive, {
            "schema_version": "empire.minimind_intent_review_queue.v1",
            "mode": "OBSERVE", "execution_authority": "none",
            "review_items": [], "outbound_authorized": False,
            "training_dataset": False,
        })  # Validate archived URLs/weak-label provenance before accepting review.
        candidates = {item["sample_ref"]: item for item in archive["review_items"]}
        sample = candidates.get(sample_ref)
        if sample is None or input_digest != sample["input_digest"]:
            raise ValueError("unknown sample or stale source content digest")
        if source_url != sample["public_review_url"]:
            raise ValueError("reviewed URL must exactly match the archived source")
        if sample["proposed_weak_label"] not in ALLOWED_CLASSES:
            raise ValueError("unrecognized archived weak classification")
        if label_path.exists():
            payload = _read_json(label_path)
            if payload.get("schema_version") != SCHEMA or not isinstance(payload.get("adjudications"), list):
                raise ValueError("invalid existing reviewer records")
            rows = payload["adjudications"]
        else:
            rows = []
        if len(rows) >= 2000:
            raise ValueError("review limit reached")
        if any(not isinstance(row, dict) or row.get("sample_ref") == sample_ref for row in rows):
            raise ValueError("sample already adjudicated; never overwrite review history")
        # Original URL is used to check the human review but deliberately not
        # stored in the label file. No raw public post text is exported.
        review_time = reviewed_at.astimezone(timezone.utc).isoformat()
        entry = {
            "sample_ref": sample_ref,
            "input_digest": input_digest,
            "label": label,
            "human_reviewed": True,
            "synthetic": False,
            "usage_scope": "EVALUATION_ONLY",
            "review_ref": "manual:" + sample_ref + ":" + review_time,
            "reviewer_ref": reviewer_ref.strip(),
            "reviewed_at": review_time,
            "review_note": review_note.strip(),
            "commercial_intent_verified": False,
            "outbound_authorized": False,
        }
        # Existing model benchmark requires an explicitly passed --adjudications
        # file: this separate record never enters the timer automatically.
        value = {"schema_version": SCHEMA, "adjudications": [*rows, entry]}
        temp_fd, temp = tempfile.mkstemp(prefix=".adjudication_", dir=label_path.parent)
        try:
            os.fchmod(temp_fd, 0o600)
            with os.fdopen(temp_fd, "w", encoding="utf-8") as handle:
                json.dump(value, handle, indent=2, sort_keys=True)
                handle.write("\n")
            os.replace(temp, label_path)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
        return {
            "schema_version": "empire.minimind_manual_review_result.v1",
            "recorded_review_count": len(value["adjudications"]),
            "review_ref": entry["review_ref"],
            "label": label,
            "outbound_authorized": False,
            "model_training_authorized": False,
            "model_promotion_authorized": False,
            "execution_authority": "none",
        }
    finally:
        os.close(fd)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--sample-ref", required=True)
    parser.add_argument("--input-digest", required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--label", choices=sorted(ALLOWED_CLASSES), required=True)
    parser.add_argument("--reviewer-ref", required=True)
    parser.add_argument("--review-note", required=True)
    parser.add_argument("--confirm-source-reviewed", action="store_true", required=True)
    args = parser.parse_args()
    result = record_review(
        root=args.repo_root, sample_ref=args.sample_ref,
        input_digest=args.input_digest, source_url=args.source_url,
        label=args.label, reviewer_ref=args.reviewer_ref,
        review_note=args.review_note,
        explicitly_reviewed=args.confirm_source_reviewed,
        reviewed_at=datetime.now(timezone.utc),
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
