"""MiniMind offline review: only explicit, source-bound human attestations."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from empire_os.minimind_intent_shadow import build_manifest, build_review_queue, merge_review_archive
from scripts.record_minimind_intent_review import record_review
from scripts.benchmark_minimind_intent import run


def _case(tmp_path):
    root = tmp_path / "runtime/community_intent"
    root.mkdir(parents=True)
    post = {
        "source": "reddit",
        "url": "https://www.reddit.com/r/smallbusiness/comments/testcase/",
        "title": "How do I generate qualified leads?",
        "text": "I own a company and need better lead generation",
        "author": "not_for_training",
    }
    history = {"schema_version": "empire.community_intent_history.v1", "observations": [post]}
    (root / "observations.json").write_text(json.dumps(history))
    run(root=tmp_path)
    archive = json.loads((root / "minimind_shadow/review_archive_latest.json").read_text())
    return archive["review_items"][0]


def _arguments(tmp_path, item):
    return {
        "root": tmp_path,
        "sample_ref": item["sample_ref"],
        "input_digest": item["input_digest"],
        "label": "OPERATOR_PROBLEM_SELF_REPORTED",
        "reviewer_ref": "founder_review_01",
        "review_note": "Independently read public post; operating problem, not purchase commitment",
        "source_url": item["public_review_url"],
        "explicitly_reviewed": True,
        "reviewed_at": datetime.now(timezone.utc),
    }


def test_explicit_review_records_one_independent_label_and_no_authority(tmp_path):
    item = _case(tmp_path)
    result = record_review(**_arguments(tmp_path, item))
    assert result["recorded_review_count"] == 1
    assert result["outbound_authorized"] is False
    assert result["model_promotion_authorized"] is False
    path = tmp_path / "runtime/community_intent/minimind_shadow/manual_adjudications.json"
    assert path.is_file() and (path.stat().st_mode & 0o777) == 0o600
    text = path.read_text()
    assert "not_for_training" not in text
    assert "https://www.reddit.com" not in text
    datum = json.loads(text)["adjudications"][0]
    assert datum["label"] == "OPERATOR_PROBLEM_SELF_REPORTED"
    assert datum["human_reviewed"] is True
    assert datum["commercial_intent_verified"] is False
    # The next normal research cycle should discover local attestations
    # without the user supplying another CLI argument or switching platforms.
    report = run(root=tmp_path)
    assert report["evaluation"]["reviewer_attested_label_count"] == 1
    assert report["historical_review_archive"]["independent_gold_label_count"] == 1
    assert report["evaluation"]["evaluation_ready"] is False
    assert report["evaluation"]["candidate_beats_baseline"] is None


@pytest.mark.parametrize("field,value,error", [
    ("explicitly_reviewed", False, "explicit"),
    ("label", "VERIFIED_BUYER", "unsupported"),
    ("source_url", "https://www.reddit.com.evil.invalid/", "exactly match"),
    ("input_digest", "a" * 64, "stale"),
    ("reviewer_ref", "", "reviewer"),
    ("review_note", "", "rationale"),
])
def test_bad_review_data_rejected_without_recording(tmp_path, field, value, error):
    item = _case(tmp_path)
    args = _arguments(tmp_path, item)
    args[field] = value
    with pytest.raises(ValueError, match=error):
        record_review(**args)
    assert not (tmp_path / "runtime/community_intent/minimind_shadow/manual_adjudications.json").exists()


def test_duplicate_review_never_overwrites_earlier_attestation(tmp_path):
    item = _case(tmp_path)
    args = _arguments(tmp_path, item)
    record_review(**args)
    path = tmp_path / "runtime/community_intent/minimind_shadow/manual_adjudications.json"
    earlier = path.read_bytes()
    with pytest.raises(ValueError, match="already adjudicated"):
        record_review(**dict(args, label="UNATTRIBUTED_DISCUSSION"))
    assert path.read_bytes() == earlier


def test_review_rejected_if_content_changed_since_last_review(tmp_path):
    item = _case(tmp_path)
    history_file = tmp_path / "runtime/community_intent/observations.json"
    history = json.loads(history_file.read_text())
    history["observations"][0]["text"] = "The owner edited their text"
    history_file.write_text(json.dumps(history))
    run(root=tmp_path)
    with pytest.raises(ValueError, match="stale"):
        record_review(**_arguments(tmp_path, item))


def test_future_old_and_naive_review_timestamps_rejected(tmp_path):
    item = _case(tmp_path)
    args = _arguments(tmp_path, item)
    for timestamp in (
        datetime.now(timezone.utc) + timedelta(days=1),
        datetime.now(timezone.utc) - timedelta(days=2),
        datetime.now().replace(tzinfo=None),
    ):
        with pytest.raises(ValueError, match="timestamp"):
            record_review(**dict(args, reviewed_at=timestamp))


def test_symlinked_label_path_never_followed(tmp_path):
    item = _case(tmp_path)
    file = tmp_path / "runtime/community_intent/minimind_shadow/manual_adjudications.json"
    trap = tmp_path / "external-secret.json"
    trap.write_text('{"secret":true}')
    file.symlink_to(trap)
    with pytest.raises(ValueError, match="unsafe label"):
        record_review(**_arguments(tmp_path, item))
    assert trap.read_text() == '{"secret":true}'


def test_unreviewed_queue_still_zero_gold_labels(tmp_path):
    item = _case(tmp_path)
    assert not (tmp_path / "runtime/community_intent/minimind_shadow/manual_adjudications.json").exists()
    report = run(root=tmp_path)
    assert report["evaluation"]["reviewer_attested_label_count"] == 0
    assert report["evaluation"]["model_training_authorized"] is False


def test_stale_manual_review_is_rejected_by_next_scheduled_shadow_evaluation(tmp_path):
    item = _case(tmp_path)
    record_review(**_arguments(tmp_path, item))
    history_file = tmp_path / "runtime/community_intent/observations.json"
    history = json.loads(history_file.read_text())
    history["observations"][0]["text"] = "Different content after human review"
    history_file.write_text(json.dumps(history))
    report = run(root=tmp_path)
    assert report["historical_review_archive"]["stale_review_attestations_quarantined"] == 1
    assert report["evaluation"]["reviewer_attested_label_count"] == 0
    assert report["evaluation"]["evaluation_ready"] is False
    assert "stale_review_attestations_excluded" in report["evaluation"]["blockers"]
    assert report["evaluation"]["candidate_beats_baseline"] is None
    assert report["outbound_sent"] is False


def test_invalid_local_review_file_cannot_be_treated_as_gold(tmp_path):
    _case(tmp_path)
    path = tmp_path / "runtime/community_intent/minimind_shadow/manual_adjudications.json"
    path.write_text(json.dumps({"schema_version":"untrusted.review.v9", "adjudications":[]}))
    with pytest.raises(ValueError, match="provenance envelope"):
        run(root=tmp_path)


def test_duplicate_local_review_rows_fail_closed(tmp_path):
    item=_case(tmp_path)
    record_review(**_arguments(tmp_path,item))
    path=tmp_path/"runtime/community_intent/minimind_shadow/manual_adjudications.json"
    payload=json.loads(path.read_text())
    payload["adjudications"].append(dict(payload["adjudications"][0]))
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError,match="duplicate local"):
        run(root=tmp_path)


def test_claimed_commercial_authority_in_manual_reviews_is_rejected(tmp_path):
    item=_case(tmp_path)
    record_review(**_arguments(tmp_path,item))
    path=tmp_path/"runtime/community_intent/minimind_shadow/manual_adjudications.json"
    payload=json.loads(path.read_text())
    payload["adjudications"][0]["outbound_authorized"]=True
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError,match="untrusted local"):
        run(root=tmp_path)
