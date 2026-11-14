#!/usr/bin/env python3
"""Bounded MiniMind intent evaluation against the existing community-intent data.

No MiniMind installation, live inference, model training, or outbound actions.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

from empire_os.minimind_intent_shadow import (
    build_manifest, build_review_queue, partition_review_attestations,
    evaluate_manifest, merge_review_archive, manifest_from_review_archive,
)

HISTORY = Path("runtime/community_intent/observations.json")
OUTPUT = Path("runtime/community_intent/minimind_shadow/latest.json")
MAX_INPUT = 2_500_000


def _safe_json(path: Path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_INPUT:
        raise ValueError("missing, symlinked or oversized MiniMind input")
    return json.loads(path.read_text(encoding="utf-8"))


def _write_private_json(target: Path, value: dict) -> None:
    if target.is_symlink() or target.parent.is_symlink():
        raise ValueError("unsafe MiniMind shadow destination")
    fd, temporary = tempfile.mkstemp(prefix=".minimind_", dir=target.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def _exclusive_shadow_lock(folder: Path):
    lock = folder / ".minimind_shadow.lock"
    if lock.is_symlink() or folder.is_symlink():
        raise ValueError("unsafe MiniMind archive lock")
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(fd, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("MiniMind archive refresh already in progress") from exc
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def run(*, root: Path, adjudications: Path | None = None, predictions: Path | None = None,
        history_payload: dict | None = None, output_path: Path | None = None):
    root = root.resolve()
    source = _safe_json(root / HISTORY) if history_payload is None else history_payload
    manifest = build_manifest(source)
    review_queue = build_review_queue(source, manifest)
    # Explicit external input remains a manual/benchmark-only override.
    # Canonical local human attestations are loaded under the archive lock.
    reviewed = _safe_json(adjudications) if adjudications is not None else None
    predicted = _safe_json(predictions) if predictions is not None else None
    if predicted is not None and (not isinstance(predicted, dict) or
            predicted.get("schema_version") != "empire.minimind_shadow_predictions.v1"):
        raise ValueError("invalid model-prediction provenance envelope")
    out = root / OUTPUT if output_path is None else Path(output_path)
    if not out.is_absolute():
        raise ValueError("shadow output override must be absolute")
    out.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if out.is_symlink() or out.parent.is_symlink():
        raise ValueError("unsafe shadow output")
    archive_path = out.parent / "review_archive_latest.json"
    with _exclusive_shadow_lock(out.parent):
        if adjudications is None:
            local_reviews = out.parent / "manual_adjudications.json"
            if local_reviews.exists() or local_reviews.is_symlink():
                reviewed = _safe_json(local_reviews)
        if reviewed is not None and reviewed.get("schema_version") != "empire.minimind_manual_adjudications.v1":
            raise ValueError("invalid adjudication provenance envelope")
        existing_archive = _safe_json(archive_path) if archive_path.exists() or archive_path.is_symlink() else None
        archive = merge_review_archive(existing_archive, review_queue)
        # Evaluate the accumulated fingerprint-only cohort, not just the 48-hour
        # source window. Stale labels always fail the input_digest check.
        evaluation_manifest = manifest_from_review_archive(archive)
        current_reviews, stale_review_count = partition_review_attestations(
            reviewed, evaluation_manifest,
        )
        report = evaluate_manifest(
            evaluation_manifest,
            adjudications=current_reviews,
            model_predictions=predicted["predictions"] if predicted is not None else None,
        )
        report["stale_review_attestations_quarantined"] = stale_review_count
        if stale_review_count:
            report["blockers"].append("stale_review_attestations_excluded")
            report["evaluation_ready"] = False
            report["candidate_beats_baseline"] = None
            report["baseline_accuracy"] = None
            report["candidate_accuracy"] = None
        payload = {"schema_version": "empire.minimind_intent_shadow_runtime.v1",
                   "manifest": manifest, "evaluation_manifest": evaluation_manifest,
                   "evaluation": report,
                   "internal_review_queue": review_queue,
                   "read_only_source": str(HISTORY),
                   "training_performed": False, "external_model_called": False,
                   "outbound_sent": False, "execution_authority": "none"}
        payload["historical_review_archive"] = {
            "schema_version": archive["schema_version"],
            "archive_count": archive["archive_count"],
            "new_items_this_cycle": archive["new_items_this_cycle"],
            "changed_content_requires_new_review": archive["changed_content_requires_new_review"],
            "baseline_label_drift_frozen": archive["baseline_label_drift_frozen"],
            "evicted_due_to_capacity": archive["evicted_due_to_capacity"],
            "independent_gold_label_count": report["reviewer_attested_label_count"],
            "stale_review_attestations_quarantined": stale_review_count,
            "outbound_authorized": False,
        }
        _write_private_json(archive_path, archive)
        _write_private_json(out, payload)
        return payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--adjudications", type=Path)
    parser.add_argument("--predictions", type=Path)
    args = parser.parse_args()
    output = run(root=Path(args.repo_root),
                 adjudications=args.adjudications, predictions=args.predictions)
    evaluation = output["evaluation"]
    print(json.dumps({
        "status": "PASS" if evaluation["evaluation_ready"] else "EVALUATION_NOT_READY",
        "source_observations": output["manifest"]["sample_count"],
        "reviewed_labels": evaluation["reviewer_attested_label_count"],
        "minimind_predictions": evaluation["candidate_prediction_count"],
        "blockers": evaluation["blockers"],
        "training_performed": False, "model_promotion_authorized": False,
        "outbound_sent": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
