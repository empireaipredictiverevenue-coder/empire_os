"""MiniMind integrates with existing public ICP history, without training or routing authority."""
from __future__ import annotations

import json

import pytest

from empire_os.minimind_intent_shadow import (
    build_manifest, build_review_queue, evaluate_manifest,
    merge_review_archive, manifest_from_review_archive,
)
from scripts.benchmark_minimind_intent import run


def observation(url="https://www.reddit.com/r/roofing/comments/one", *,
                title="I need help with roofing leads", text="I own a roofing company"):
    return {
        "source": "reddit", "url": url, "title": title, "text": text,
        "author": "someuser", "pain_points": ["not_a_real_proof"],
    }


def history(rows=None):
    return {"schema_version": "empire.community_intent_history.v1",
            "observations": [observation()] if rows is None else rows}


def test_public_observation_yields_non_identifying_review_manifest():
    manifest = build_manifest(history())
    assert manifest["sample_count"] == 1
    assert manifest["raw_post_content_exported"] is False
    row = manifest["samples"][0]
    assert row["baseline_intent_class"] == "EXPLICIT_REQUEST_UNVERIFIED"
    assert row["label_source"] == "DETERMINISTIC_WEAK_BASELINE_NOT_GOLD"
    assert not any(key in row for key in ("author", "title", "text", "url"))
    assert manifest["model_training_authorized"] is False
    assert evaluate_manifest(manifest)["baseline_accuracy"] is None


def test_changed_post_cannot_reuse_prior_adjudication():
    row = observation()
    old = build_manifest(history([row]))["samples"][0]
    changed = build_manifest(history([observation(text="Edited message!")]))["samples"][0]
    assert old["sample_ref"] == changed["sample_ref"]
    assert old["input_digest"] != changed["input_digest"]
    gold = [{
        "sample_ref": old["sample_ref"], "input_digest": old["input_digest"],
        "label": "EXPLICIT_REQUEST_UNVERIFIED", "human_reviewed": True,
        "review_ref": "review:one", "synthetic": False, "usage_scope": "EVALUATION_ONLY",
    }]
    with pytest.raises(ValueError, match="digest"):
        evaluate_manifest(build_manifest(history([observation(text="Edited message!")])),
                          adjudications=gold)


def test_source_spoof_or_non_https_excluded():
    manifest = build_manifest(history([
        observation("https://www.reddit.com.evil.invalid/post"),
        observation("http://www.reddit.com/post"),
        observation("https://www.reddit.com@evil.invalid/post"),
    ]))
    assert manifest["sample_count"] == 0


def test_conflicting_versions_same_source_are_not_silently_merged():
    with pytest.raises(ValueError, match="ambiguous"):
        build_manifest(history([observation(), observation(text="different")]))


def test_baseline_itself_is_never_independent_gold():
    m = build_manifest(history())
    baseline = m["samples"][0]
    preds = [{
        "sample_ref": baseline["sample_ref"], "input_digest": baseline["input_digest"],
        "label": baseline["baseline_intent_class"], "model_family": "minimind",
        "model_version": "shadow-test", "shadow_only": True,
    }]
    result = evaluate_manifest(m, model_predictions=preds)
    assert result["reviewer_attested_label_count"] == 0
    assert result["candidate_beats_baseline"] is None
    assert not result["model_promotion_authorized"]


def test_duplicate_or_fake_review_rejected():
    m = build_manifest(history())
    row = m["samples"][0]
    base = dict(sample_ref=row["sample_ref"], input_digest=row["input_digest"],
                label=row["baseline_intent_class"], human_reviewed=True,
                review_ref="review:one", synthetic=False, usage_scope="EVALUATION_ONLY")
    with pytest.raises(ValueError, match="duplicated"):
        evaluate_manifest(m, adjudications=[base, base])
    with pytest.raises(ValueError, match="unreviewed"):
        evaluate_manifest(m, adjudications=[dict(base, human_reviewed=False)])


def test_small_human_review_cohort_does_not_claim_win():
    m = build_manifest(history())
    row = m["samples"][0]
    ref, digest = row["sample_ref"], row["input_digest"]
    gold = [dict(sample_ref=ref, input_digest=digest,
                 label="EXPLICIT_REQUEST_UNVERIFIED", human_reviewed=True,
                 synthetic=False, usage_scope="EVALUATION_ONLY", review_ref="review:one")]
    preds = [dict(sample_ref=ref, input_digest=digest,
                  label="EXPLICIT_REQUEST_UNVERIFIED", model_family="minimind",
                  model_version="shadow", shadow_only=True)]
    result = evaluate_manifest(m, adjudications=gold, model_predictions=preds)
    assert result["matched_evaluation_count"] == 1
    assert result["evaluation_ready"] is False
    assert result["candidate_beats_baseline"] is None


def test_cli_runs_without_minimind_runtime_and_writes_private_file(tmp_path):
    directory = tmp_path / "runtime/community_intent"
    directory.mkdir(parents=True)
    (directory / "observations.json").write_text(json.dumps(history()))
    report = run(root=tmp_path)
    assert report["manifest"]["sample_count"] == 1
    assert report["evaluation"]["evaluation_ready"] is False
    assert report["external_model_called"] is False
    assert report["training_performed"] is False
    assert report["outbound_sent"] is False
    path = directory / "minimind_shadow/latest.json"
    assert path.is_file() and path.stat().st_mode & 0o777 == 0o600


def test_cli_rejects_symlink_history(tmp_path):
    directory = tmp_path / "runtime/community_intent"
    directory.mkdir(parents=True)
    other = tmp_path / "other.json"
    other.write_text(json.dumps(history()))
    (directory / "observations.json").symlink_to(other)
    with pytest.raises(ValueError, match="symlinked"):
        run(root=tmp_path)


def test_private_review_queue_prioritizes_unverified_requests_without_gold_labels():
    rows = [observation("https://www.reddit.com/r/roofing/comments/b?utm_source=x"),
            observation("https://www.reddit.com/r/roofing/comments/a",
                        title="We can build your ads", text="We offer lead generation") ]
    h = history(rows)
    m = build_manifest(h)
    queue = build_review_queue(h, m)
    assert queue["review_queue_count"] == 2
    assert queue["review_items"][0]["review_priority"] == "HIGH"
    assert queue["review_items"][0]["public_review_url"].endswith("/comments/b")
    assert queue["independent_gold_labels_collected"] == 0
    assert queue["contains_raw_post_text"] is False
    assert queue["training_dataset"] is False
    assert all(row["independent_gold_label"] is None for row in queue["review_items"])
    assert all("text" not in row and "author" not in row for row in queue["review_items"])


def test_spoofed_sources_cannot_enter_internal_review_queue():
    h = history([observation("https://www.reddit.com.evil.invalid/landing")])
    manifest = build_manifest(h)
    assert build_review_queue(h, manifest)["review_queue_count"] == 0


def test_archive_keeps_sources_after_48_hour_history_rolls_off(tmp_path):
    path = tmp_path / "runtime/community_intent/observations.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(history()))
    first = run(root=tmp_path)
    assert first["manifest"]["sample_count"] == 1
    assert first["evaluation_manifest"]["sample_count"] == 1
    path.write_text(json.dumps(history([])))
    second = run(root=tmp_path)
    assert second["manifest"]["sample_count"] == 0
    assert second["evaluation_manifest"]["sample_count"] == 1
    assert second["historical_review_archive"]["archive_count"] == 1
    assert second["evaluation"]["reviewer_attested_label_count"] == 0
    archive = path.parent / "minimind_shadow/review_archive_latest.json"
    assert archive.exists() and archive.stat().st_mode & 0o777 == 0o600
    assert "someuser" not in archive.read_text()
    assert "I own a roofing" not in archive.read_text()


def test_changed_post_updates_digest_and_invalidates_old_review(tmp_path):
    path = tmp_path / "runtime/community_intent/observations.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(history()))
    previous = run(root=tmp_path)
    old = previous["manifest"]["samples"][0]
    path.write_text(json.dumps(history([observation(text="changed later")])) )
    current = run(root=tmp_path)
    assert current["historical_review_archive"]["archive_count"] == 1
    assert current["historical_review_archive"]["changed_content_requires_new_review"] == 1
    newer = current["evaluation_manifest"]["samples"][0]
    assert newer["sample_ref"] == old["sample_ref"]
    assert newer["input_digest"] != old["input_digest"]
    labels = {"schema_version":"empire.minimind_manual_adjudications.v1",
              "adjudications":[{
                   "sample_ref":old["sample_ref"], "input_digest":old["input_digest"],
                   "label":"EXPLICIT_REQUEST_UNVERIFIED","human_reviewed":True,
                   "review_ref":"review:old", "synthetic":False,
                   "usage_scope":"EVALUATION_ONLY"}]}
    review_file = tmp_path / "old_review.json"
    review_file.write_text(json.dumps(labels))
    # An outdated, originally human-attested label is quarantined and never
    # counted as current gold, while the research collector remains healthy.
    report = run(root=tmp_path, adjudications=review_file)
    assert report["evaluation"]["stale_review_attestations_quarantined"] == 1
    assert report["evaluation"]["reviewer_attested_label_count"] == 0
    assert not report["evaluation"]["evaluation_ready"]
    assert report["evaluation"]["candidate_beats_baseline"] is None


def test_archive_capacity_and_unsafe_replay_fail_closed():
    h=history()
    m=build_manifest(h)
    latest=build_review_queue(h,m)
    archive=merge_review_archive(None,latest,max_samples=1)
    assert archive["archive_count"]==1
    assert manifest_from_review_archive(archive)["sample_count"]==1
    bad=dict(archive,outbound_authorized=True)
    with pytest.raises(ValueError,match="unsafe"):
        merge_review_archive(bad,latest,max_samples=1)
    with pytest.raises(ValueError,match="capacity"):
        merge_review_archive(None,latest,max_samples=0)


def test_archive_symlink_blocked_and_no_shadow_update(tmp_path):
    path=tmp_path/"runtime/community_intent/observations.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(history()))
    output=path.parent/"minimind_shadow"
    output.mkdir()
    external=tmp_path/"external.json"
    external.write_text("{}")
    (output/"review_archive_latest.json").symlink_to(external)
    with pytest.raises(ValueError,match="symlinked"):
        run(root=tmp_path)
    assert external.read_text()=="{}"


def test_baseline_label_drift_is_recorded_not_retrospectively_rewritten():
    h = history()
    original = build_review_queue(h, build_manifest(h))
    archive = merge_review_archive(None, original)
    same_content_new_rule = json.loads(json.dumps(original))
    same_content_new_rule["review_items"][0]["proposed_weak_label"] = "NON_COMMERCIAL_HIRING_OR_CAREER"
    next_archive = merge_review_archive(archive, same_content_new_rule)
    assert next_archive["baseline_label_drift_frozen"] == 1
    assert next_archive["review_items"][0]["proposed_weak_label"] == original["review_items"][0]["proposed_weak_label"]
    assert manifest_from_review_archive(next_archive)["samples"][0]["baseline_intent_class"] == original["review_items"][0]["proposed_weak_label"]


def test_noncommercial_hiring_category_is_supported_without_claiming_buyer_intent():
    h=history([observation(title="[Hiring] Sales manager role", text="We're hiring a territory account manager")])
    m=build_manifest(h)
    assert m["samples"][0]["baseline_intent_class"] == "NON_COMMERCIAL_HIRING_OR_CAREER"
    q=build_review_queue(h,m)
    assert q["review_items"][0]["review_priority"] == "LOW"
    assert merge_review_archive(None,q)["outbound_authorized"] is False


def test_second_concurrent_shadow_writer_rejected_without_data_loss(tmp_path):
    import fcntl
    import os
    root=tmp_path/"runtime/community_intent"
    root.mkdir(parents=True)
    (root/"observations.json").write_text(json.dumps(history()))
    before=run(root=tmp_path)
    latest=root/"minimind_shadow/latest.json"
    previous=latest.read_bytes()
    lock=root/"minimind_shadow/.minimind_shadow.lock"
    fd=os.open(lock,os.O_RDWR|os.O_NOFOLLOW)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with pytest.raises(ValueError,match="already in progress"):
            run(root=tmp_path)
        assert latest.read_bytes()==previous
    finally:
        fcntl.flock(fd,fcntl.LOCK_UN)
        os.close(fd)
    assert run(root=tmp_path)["historical_review_archive"]["archive_count"]==1
