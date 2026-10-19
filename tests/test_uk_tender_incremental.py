"""Cursor-safe, time-frozen and non-commercial UK OCDS incremental tests."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
import json

import pytest

from empire_os.uk_tender_incremental import (
    SCHEMA, STAGE_PATH, TenderIncrementalHold, _source_url,
    advance_one_public_page, advance_private_checkpoint, empty_checkpoint,
)
from empire_os.uk_public_tender_observer import BASE
from test_public_source_sweep import tender

NOW = datetime(2026, 10, 18, 22, 45, tzinfo=timezone.utc)


def page(*, cursor=None, from_time=None, to_time=None, rows=None, change=None):
    doc = tender()
    if rows is not None:
        doc["releases"] = rows
    if change:
        change(doc)
    if cursor:
        begin = from_time or (NOW - timedelta(hours=24,minutes=5)).strftime("%Y-%m-%dT%H:%M:%S")
        end = to_time or (NOW - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S")
        doc["links"] = {"next": _source_url(begin, end, cursor)}
    return json.dumps(doc).encode()


def first_page():
    return lambda start, end, cursor: page(
        cursor="abcXYZ001==", from_time=start, to_time=end,
        rows=tender()["releases"][:1],
    )


def test_first_incremental_page_keeps_high_watermark_held():
    original = empty_checkpoint()
    observed = []
    def fetch(start, end, cursor):
        observed.append((start,end,cursor))
        return page(cursor="abcXYZ001==", from_time=start,
                    to_time=end, rows=tender()["releases"][:1])
    new, review = advance_one_public_page(original, as_of=NOW, fetch_page=fetch)
    assert original == empty_checkpoint()
    assert len(observed) == 1
    assert observed[0][2] is None
    assert new["last_complete_window_end"] is None
    assert new["inflight"]["next_cursor"] == "abcXYZ001=="
    assert new["inflight"]["page_count"] == 1
    assert len(new["inflight"]["seen"]) == 1
    assert review["status"] == "INCOMPLETE_WINDOW_CURSOR_STAGED"
    assert review["window_high_watermark_promoted"] is False
    assert review["source_change_counts_on_this_page"] == {
        "NEW_PUBLIC_PROCUREMENT_PROCESS": 1,
    }
    assert review["recognized_revenue"] is False


def test_resume_cursor_promotes_only_final_page_and_dedupes_process():
    previous, _ = advance_one_public_page(
        empty_checkpoint(), as_of=NOW, fetch_page=first_page()
    )
    called = []
    def end(start, finish, cursor):
        called.append(cursor)
        assert cursor == "abcXYZ001=="
        return page(rows=[tender()["releases"][0],tender()["releases"][1]])
    finished, review = advance_one_public_page(
        previous, as_of=NOW, fetch_page=end
    )
    assert called == ["abcXYZ001=="]
    assert review["status"] == "COMPLETE_WINDOW_REVIEW"
    assert review["source_change_counts_on_this_page"] == {
        "NEW_PUBLIC_PROCUREMENT_PROCESS": 1,
        "REPEATED_IDENTICAL_RELEASE": 1,
    }
    assert len(finished["recent"]) == 2
    assert finished["inflight"] is None
    assert finished["last_complete_window_end"] == (NOW - timedelta(days=7,minutes=5) + timedelta(hours=4)).strftime("%Y-%m-%dT%H:%M:%S")


def test_repeated_window_does_not_create_new_procurement_or_fake_revenue():
    state, _ = advance_one_public_page(
        empty_checkpoint(), as_of=NOW, fetch_page=lambda *args: page(),
    )
    assert state["inflight"] is None
    next_state, review = advance_one_public_page(
        state, as_of=NOW + timedelta(hours=1),
        fetch_page=lambda *args: page(),
    )
    assert review["source_change_counts_on_this_page"] == {
        "REPEATED_IDENTICAL_RELEASE": 2,
    }
    assert review["non_identical_source_evidence"] == []
    assert len(next_state["recent"]) == 2
    assert review["buyer_terms_verified"] is False


def test_same_release_semantic_amendment_is_a_revision_not_sale():
    state, _ = advance_one_public_page(
        empty_checkpoint(), as_of=NOW, fetch_page=lambda *args: page(),
    )
    changed = tender()
    changed["releases"][0]["tender"]["status"] = "complete"
    changed["releases"][0]["tender"]["tenderPeriod"]["endDate"] = "2026-11-30T00:00:00Z"
    revised, review = advance_one_public_page(
        state, as_of=NOW + timedelta(hours=1),
        fetch_page=lambda *args: json.dumps(changed).encode(),
    )
    assert review["source_change_counts_on_this_page"] == {
        "CHANGED_EXISTING_RELEASE": 1,
        "REPEATED_IDENTICAL_RELEASE": 1,
    }
    assert any(row["change_class"] == "CHANGED_EXISTING_RELEASE"
               for row in review["non_identical_source_evidence"])
    assert all(row["award_or_revenue_verified"] is False for row in review["non_identical_source_evidence"])


def test_new_release_to_known_ocid_does_not_count_as_new_procurement():
    state, _ = advance_one_public_page(
        empty_checkpoint(), as_of=NOW, fetch_page=lambda *args: page(),
    )
    variant = deepcopy(tender()["releases"][0])
    variant["id"] = "012349-2026-release3"
    _, review = advance_one_public_page(
        state, as_of=NOW + timedelta(hours=1),
        fetch_page=lambda *args: page(rows=[variant]),
    )
    assert review["source_change_counts_on_this_page"] == {
        "NEW_RELEASE_EXISTING_PROCESS": 1,
    }


@pytest.mark.parametrize("next_url", [
    "https://evil.example.com/api/1.0/ocdsReleasePackages?cursor=ABC",
    "http://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages?cursor=ABC",
    "https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages?cursor=ABC",
    "https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages?limit=5&stages=award&updatedFrom=2026-10-01T00:00:00&updatedTo=2026-10-18T00:00:00&cursor=abc",
    "https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages?limit=5&stages=tender&updatedFrom=2026-10-01T00:00:00&updatedTo=2026-10-18T00:00:00&cursor=abc&password=secret",
])
def test_hostile_or_drifting_provider_next_link_held(next_url):
    original = empty_checkpoint()
    def invalid(*args):
        doc = tender()
        doc["links"] = {"next": next_url}
        return json.dumps(doc).encode()
    with pytest.raises(TenderIncrementalHold):
        advance_one_public_page(original, as_of=NOW, fetch_page=invalid)
    assert original == empty_checkpoint()


def test_cursor_self_loop_refused():
    start, _ = advance_one_public_page(
        empty_checkpoint(), as_of=NOW, fetch_page=first_page()
    )
    with pytest.raises(TenderIncrementalHold, match="no progress"):
        advance_one_public_page(start, as_of=NOW, fetch_page=first_page())


def test_partial_checkpoint_requires_explicit_apply_and_is_atomic(tmp_path):
    def fetch(start, end, cursor):
        return page(cursor="abcXYZ001==", from_time=start, to_time=end,
                    rows=tender()["releases"][:1])
    preview = advance_private_checkpoint(
        tmp_path, as_of=NOW, fetch_page=fetch, test_only=True,
    )
    assert preview["checkpoint_written"] is False
    target = tmp_path/STAGE_PATH
    assert not target.exists()
    applied = advance_private_checkpoint(
        tmp_path, as_of=NOW, apply=True, fetch_page=fetch, test_only=True,
    )
    assert applied["checkpoint_written"] is True
    assert target.is_file() and target.stat().st_mode & 0o777 == 0o600
    contents = json.loads(target.read_text())
    assert contents["inflight"]["page_count"] == 1
    assert contents["last_complete_window_end"] is None
    completed = advance_private_checkpoint(
        tmp_path, as_of=NOW, apply=True,
        fetch_page=lambda *args: page(rows=tender()["releases"][1:]),
        test_only=True,
    )
    assert completed["status"] == "COMPLETE_WINDOW_REVIEW"
    assert json.loads(target.read_text())["inflight"] is None


def test_failed_incremental_page_does_not_advance_on_disk(tmp_path):
    def bad(*args):
        raise TenderIncrementalHold("rate limited")
    with pytest.raises(TenderIncrementalHold, match="rate limited"):
        advance_private_checkpoint(
            tmp_path, as_of=NOW, apply=True, fetch_page=bad, test_only=True,
        )
    assert not (tmp_path/STAGE_PATH).exists()


def test_untrusted_or_future_checkpoint_is_held():
    state = empty_checkpoint()
    state["last_complete_window_end"] = "2099-01-01T00:00:00"
    with pytest.raises(TenderIncrementalHold, match="future"):
        advance_one_public_page(
            state, as_of=NOW, fetch_page=lambda *args: page()
        )
    state = empty_checkpoint()
    state["recent"] = {"not-a-hash":{"semantic_digest":"bad","ocid_digest":"also-bad"}}
    with pytest.raises(TenderIncrementalHold):
        advance_one_public_page(state, as_of=NOW, fetch_page=lambda *args: page())


def test_one_page_response_does_not_leak_original_party_or_free_text():
    state, review = advance_one_public_page(
        empty_checkpoint(), as_of=NOW, fetch_page=lambda *args: page()
    )
    summary = json.dumps([state,review])
    for private in ("PRIVATE_BUYER_CONTACT", "never@exported.com", "PRIVATE_DESCRIPTION_SECRET"):
        assert private not in summary
    assert review["contact_extracted"] is False


def test_prod_state_file_cannot_be_written_from_noncanonical_worktree(tmp_path):
    with pytest.raises(PermissionError, match="feature worktree"):
        advance_private_checkpoint(
            tmp_path, as_of=NOW, apply=True,
            fetch_page=lambda *args: page()
        )
    assert not (tmp_path/STAGE_PATH).exists()


def test_bounded_full_page_without_cursor_is_not_complete_source_coverage():
    populated = tender()["releases"]
    five = []
    for index in range(5):
        notice = deepcopy(populated[0])
        notice["id"] = f"1111{index}-2026"
        notice["ocid"] = f"ocds-h6vhtk-a1b2c{index}"
        five.append(notice)
    with pytest.raises(TenderIncrementalHold, match="completion pagination"):
        advance_one_public_page(
            empty_checkpoint(), as_of=NOW,
            fetch_page=lambda *args: page(rows=five),
        )


def test_source_sector_packets_only_use_official_cpv_and_not_supplier_contacts():
    _, review = advance_one_public_page(
        empty_checkpoint(), as_of=NOW,
        fetch_page=lambda *args: page(),
    )
    research = review["sector_research"]
    assert research["status"] == "SECTOR_RESEARCH_CANDIDATES"
    assert research["candidate_count_in_bounded_page"] == 1
    candidate = research["candidates"][0]
    assert candidate["sector_codes_matched"] == ["solar"]
    assert candidate["source_window_complete"] is True
    assert candidate["independent_current_notice_and_eligibility_check_required"] is True
    assert candidate["recognized_revenue_or_award"] is False
    assert candidate["outbound_or_bid_authorized"] is False
    assert research["new_crm_records_created"] is False
    for prohibited in ("PRIVATE PERSON", "PRIVATE_BUYER_CONTACT", "never@exported.com"):
        assert prohibited not in json.dumps(research)


def test_private_preview_cannot_claim_persisted_watermark(tmp_path):
    _, review = advance_one_public_page(
        empty_checkpoint(), as_of=NOW, fetch_page=lambda *args: page(),
    )
    assert review["window_high_watermark_promoted"] is True  # proposed state only
    actual = advance_private_checkpoint(
        tmp_path, as_of=NOW, fetch_page=lambda *args: page(),
        test_only=True,
    )
    assert actual["status"] == "PREVIEW_COMPLETE_WINDOW_REVIEW"
    assert actual["window_would_complete_if_applied"] is True
    assert actual["window_high_watermark_promoted"] is False
    assert actual["checkpoint_written"] is False
    assert not (tmp_path/STAGE_PATH).exists()


def test_source_error_during_inflight_resume_preserves_last_cursor(tmp_path):
    def first(start, end, cursor):
        return page(cursor="lastGoodCursor1==", from_time=start,
                    to_time=end, rows=tender()["releases"][:1])
    advance_private_checkpoint(
        tmp_path, as_of=NOW, apply=True,
        fetch_page=first, test_only=True,
    )
    path = tmp_path/STAGE_PATH
    before = path.read_bytes()
    def bad(*args):
        data = tender()
        data["links"] = {"next": "https://evil.example.org/steal?secret=1"}
        return json.dumps(data).encode()
    with pytest.raises(TenderIncrementalHold):
        advance_private_checkpoint(
            tmp_path, as_of=NOW, apply=True,
            fetch_page=bad, test_only=True,
        )
    assert path.read_bytes() == before


def test_private_checkpoint_health_aggregates_without_cursors_or_contacts(tmp_path):
    from empire_os.uk_tender_incremental import review_incremental_checkpoint
    missing = review_incremental_checkpoint(tmp_path, as_of=NOW)
    assert missing["status"] == "NOT_ACTIVATED"
    assert missing["inflight_page_count"] is None
    assert missing["complete_source_coverage_claimed"] is False
    def fetch(start, end, cursor):
        return page(cursor="abcXYZ001==", from_time=start, to_time=end,
                    rows=tender()["releases"][:1])
    advance_private_checkpoint(
        tmp_path, as_of=NOW, apply=True, fetch_page=fetch, test_only=True
    )
    result = review_incremental_checkpoint(tmp_path, as_of=NOW)
    assert result["status"] == "PARTIAL_BACKFILL"
    assert result["inflight_page_count"] == 1
    assert result["inflight_source_records"] == 1
    assert result["completed_source_receipt_count"] == 0
    assert result["last_complete_window_end"] is None
    assert result["complete_source_coverage_claimed"] is False
    assert "abcXYZ001" not in json.dumps(result)
    assert "PRIVATE" not in json.dumps(result)


def test_staged_health_is_visible_via_existing_revenue_stream_mining(tmp_path):
    from empire_os.revenue_stream_mining import build_revenue_stream_mining
    from empire_os.uk_tender_incremental import review_incremental_checkpoint
    first = build_revenue_stream_mining(tmp_path, as_of=NOW)
    assert first["source_discovery"]["uk_tender_incremental"]["status"] == "NOT_ACTIVATED"
    advance_private_checkpoint(
        tmp_path, as_of=NOW, apply=True, test_only=True,
        fetch_page=lambda start, end, cursor: page(
            cursor="newCursor001==", from_time=start, to_time=end,
            rows=tender()["releases"][:1]
        )
    )
    after = build_revenue_stream_mining(tmp_path, as_of=NOW)
    health = after["source_discovery"]["uk_tender_incremental"]
    assert health["status"] == "PARTIAL_BACKFILL"
    assert health["inflight_source_records"] == 1
    assert after["worker_dispatched"] is False
    assert after["source_discovery"]["source_polling_started"] is False


def test_trusted_checkpoint_health_holds_corrupt_source(tmp_path):
    from empire_os.uk_tender_incremental import review_incremental_checkpoint
    target = tmp_path/STAGE_PATH
    target.parent.mkdir(parents=True)
    target.write_text('{"tampered":true}')
    result = review_incremental_checkpoint(tmp_path, as_of=NOW)
    assert result["status"] == "UNTRUSTED_PRIVATE_CHECKPOINT"
    assert result["inflight_page_count"] is None
    assert result["next_cursor_or_identifiers_exposed"] is False


def test_sector_review_outbox_commits_atomically_with_partial_cursor(tmp_path):
    from empire_os.uk_tender_incremental import deliver_one_pending_sector_review
    def first(start,end,cursor):
        return page(cursor="testCursor001==",from_time=start,to_time=end,
                    rows=tender()["releases"][:1])
    result = advance_private_checkpoint(
        tmp_path, as_of=NOW, apply=True, fetch_page=first, test_only=True,
    )
    assert result["window_high_watermark_promoted"] is False
    assert result["pending_sector_research_count"] == 1
    state = json.loads((tmp_path/STAGE_PATH).read_text())
    assert len(state["pending_sector_research"]) == 1
    assert state["last_complete_window_end"] is None
    assert "never@exported.com" not in json.dumps(state)
    preview = deliver_one_pending_sector_review(tmp_path, as_of=NOW, test_only=True)
    assert preview["status"] == "REVIEW_ONLY"
    assert preview["queued"] is False
    assert preview["pending"] == 1
    assert not (tmp_path/"runtime/departments/work").exists()


def test_pending_sector_queue_retries_without_double_send_or_duplicate_job(tmp_path):
    from empire_os.uk_tender_incremental import deliver_one_pending_sector_review
    advance_private_checkpoint(
        tmp_path, as_of=NOW, apply=True,
        fetch_page=lambda *args: page(rows=tender()["releases"][:1]),
        test_only=True,
    )
    state_path = tmp_path/STAGE_PATH
    original = json.loads(state_path.read_text())
    assert len(original["pending_sector_research"]) == 1
    work_key = next(iter(original["pending_sector_research"]))
    prior = deliver_one_pending_sector_review(
        tmp_path, as_of=NOW, apply=True, test_only=True,
        department_repo_root=tmp_path,
    )
    assert prior["status"] == "QUEUED"
    assert prior["pending"] == 0
    assert prior["outbound_sent"] is False
    files = list((tmp_path/"runtime/departments/work/ready").glob("*.json"))
    assert len(files) == 1
    job = json.loads(files[0].read_text())
    assert job["authority"] == "observe"
    assert job["intelligence_request"]["budget"]["requested_external_cost_cents"] == 0
    assert job["intelligence_request"]["official_tender_source_review"]["crm_admission_authorized"] is False
    assert "never@exported.com" not in json.dumps(job)
    assert json.loads(state_path.read_text())["pending_sector_research"] == {}
    # Simulate crash after queue insertion, before acknowledgement: restore
    # ONLY the private pending outbox, preserving the already-queued work.
    state_path.write_text(json.dumps(original))
    replay = deliver_one_pending_sector_review(
        tmp_path, as_of=NOW, apply=True, test_only=True,
        department_repo_root=tmp_path,
    )
    assert replay["status"] == "ALREADY_QUEUED"
    assert replay["queued"] is False
    assert len(list((tmp_path/"runtime/departments/work/ready").glob("*.json"))) == 1
    assert json.loads(state_path.read_text())["pending_sector_research"] == {}
    assert work_key not in json.dumps(replay)
    assert deliver_one_pending_sector_review(
        tmp_path, as_of=NOW, apply=True,
        department_repo_root=tmp_path, test_only=True,
    )["status"] == "NO_PENDING_RESEARCH"


def test_pending_sector_queue_failure_keeps_original_outbox(tmp_path, monkeypatch):
    from empire_os.uk_tender_incremental import deliver_one_pending_sector_review
    from empire_os.department_work_queue import DepartmentWorkQueue
    advance_private_checkpoint(
        tmp_path, as_of=NOW, apply=True, test_only=True,
        fetch_page=lambda *args: page(rows=tender()["releases"][:1]),
    )
    before = (tmp_path/STAGE_PATH).read_bytes()
    def fail(*args, **kwargs):
        raise RuntimeError("existing queue temporarily unavailable")
    monkeypatch.setattr(DepartmentWorkQueue, "enqueue_step", fail)
    with pytest.raises(RuntimeError, match="temporarily"):
        deliver_one_pending_sector_review(
            tmp_path, as_of=NOW, apply=True,
            department_repo_root=tmp_path, test_only=True,
        )
    assert (tmp_path/STAGE_PATH).read_bytes() == before


@pytest.mark.parametrize("bad", [
    {"verticals": ["roofing", "untrusted-sector"]},
    {"source_ref": "https://evil.example.com/contacts"},
    {"release_digest": "invalid"},
    {"source_window_complete": "yes"},
])
def test_tampered_research_outbox_held_without_queue(tmp_path, bad):
    from empire_os.uk_tender_incremental import deliver_one_pending_sector_review
    advance_private_checkpoint(
        tmp_path, as_of=NOW, apply=True, test_only=True,
        fetch_page=lambda *args: page(rows=tender()["releases"][:1]),
    )
    path = tmp_path/STAGE_PATH
    state = json.loads(path.read_text())
    pending = next(iter(state["pending_sector_research"].values()))
    pending.update(bad)
    path.write_text(json.dumps(state))
    with pytest.raises(TenderIncrementalHold):
        deliver_one_pending_sector_review(
            tmp_path, as_of=NOW, apply=True,
            department_repo_root=tmp_path, test_only=True,
        )
    assert not (tmp_path/"runtime/departments/work").exists()


def test_research_pending_does_not_claim_production_dataset_or_activation(tmp_path):
    from empire_os.uk_tender_incremental import review_incremental_checkpoint
    advance_private_checkpoint(
        tmp_path, as_of=NOW, apply=True, test_only=True,
        fetch_page=lambda *args: page(rows=tender()["releases"][:1]),
    )
    health = review_incremental_checkpoint(tmp_path, as_of=NOW)
    assert health["pending_sector_research_count"] == 1
    assert health["source_polling_scheduled"] is False
    assert health["complete_source_coverage_claimed"] is False
    assert health["provider_worker_running"] is False


def test_initial_seven_day_backfill_uses_contiguous_four_hour_partitions():
    calls = []
    def empty(start, end, cursor):
        calls.append((start, end, cursor))
        return page(rows=[])
    state = empty_checkpoint()
    for index in range(3):
        state, result = advance_one_public_page(state, as_of=NOW, fetch_page=empty)
        assert result["bounded_partition_complete"] is True
        assert result["source_update_window_is_global_complete"] is False
        assert result["window_high_watermark_promoted"] is True
        assert state["inflight"] is None
    for index, (start, end, cursor) in enumerate(calls):
        assert cursor is None
        from datetime import datetime as D
        parsed_start = D.fromisoformat(start)
        parsed_end = D.fromisoformat(end)
        assert parsed_end > parsed_start
        assert parsed_end - parsed_start <= timedelta(hours=4, minutes=5)
        if index:
            assert parsed_start == D.fromisoformat(calls[index-1][1]) - timedelta(minutes=5)
    assert state["last_complete_window_end"] == calls[-1][1]
    assert D.fromisoformat(calls[0][0]) == (
        NOW - timedelta(days=7, minutes=5)
    ).replace(tzinfo=None)


def test_original_v1_partial_cursor_preserved_when_v2_starts(tmp_path):
    from empire_os.uk_tender_incremental import LEGACY_STAGE_PATH
    old = tmp_path / LEGACY_STAGE_PATH
    old.parent.mkdir(parents=True,exist_ok=True)
    old.write_text('{"legacy":"do not destroy historical source receipts"}')
    advance_private_checkpoint(
        tmp_path, as_of=NOW, test_only=True, apply=True,
        fetch_page=lambda *args: page(rows=[]),
    )
    assert "do not destroy" in old.read_text()
    assert (tmp_path/STAGE_PATH).exists()
    assert old != tmp_path/STAGE_PATH


def test_source_revisions_detect_changed_requirements_with_same_status_cpv_and_deadline():
    state, _ = advance_one_public_page(
        empty_checkpoint(), as_of=NOW, fetch_page=lambda *args: page()
    )
    updated = tender()
    updated["releases"][0]["tender"]["description"] = (
        "REVISED PROCUREMENT REQUIREMENTS — PRIVATE FREE TEXT"
    )
    _, review = advance_one_public_page(
        state, as_of=NOW+timedelta(hours=1),
        fetch_page=lambda *args: json.dumps(updated).encode()
    )
    assert review["source_change_counts_on_this_page"] == {
        "CHANGED_EXISTING_RELEASE": 1, "REPEATED_IDENTICAL_RELEASE": 1
    }
    assert "REVISED PROCUREMENT REQUIREMENTS" not in json.dumps(review)
    assert review["recognized_revenue"] is False


def test_backfill_status_cannot_masquerade_as_caught_up(tmp_path):
    from empire_os.uk_tender_incremental import review_incremental_checkpoint
    advance_private_checkpoint(
        tmp_path, as_of=NOW, apply=True, test_only=True,
        fetch_page=lambda *args: page(rows=[]),
    )
    health = review_incremental_checkpoint(tmp_path, as_of=NOW)
    assert health["status"] == "BACKFILL_BEHIND_CURRENT_WINDOW"
    assert health["backfill_remaining_hours"] > 24
    assert health["caught_up_to_latest_safe_window"] is False
    assert health["complete_source_coverage_claimed"] is False


def test_previous_generation_created_and_recoverable_only_explicitly(tmp_path):
    from empire_os.uk_tender_incremental import (
        _private_backup, recover_previous_private_checkpoint, review_incremental_checkpoint
    )
    state_path = tmp_path/STAGE_PATH
    first = advance_private_checkpoint(
        tmp_path, as_of=NOW, apply=True, test_only=True,
        fetch_page=lambda *args: page(rows=[]),
    )
    assert first["checkpoint_written"] is True
    original = state_path.read_bytes()
    assert not _private_backup(state_path).exists()
    second = advance_private_checkpoint(
        tmp_path, as_of=NOW+timedelta(hours=1), apply=True, test_only=True,
        fetch_page=lambda *args: page(rows=tender()["releases"][:1]),
    )
    assert second["checkpoint_written"] is True
    backup = _private_backup(state_path)
    assert backup.read_bytes() == original
    assert backup.stat().st_mode & 0o777 == 0o600
    assert state_path.read_bytes() != original
    with pytest.raises(TenderIncrementalHold, match="active checkpoint valid"):
        recover_previous_private_checkpoint(tmp_path, as_of=NOW+timedelta(hours=1),
                                            apply=True, test_only=True)
    corrupted = b'{"corrupt_source":"contact-secret@example.com"}'
    state_path.write_bytes(corrupted)
    health = review_incremental_checkpoint(tmp_path, as_of=NOW+timedelta(hours=1))
    assert health["status"] == "UNTRUSTED_PRIVATE_CHECKPOINT"
    assert health["previous_checkpoint_recovery"] == "PREVIOUS_GENERATION_VALIDATED"
    assert health["next_safe_operator_action"] == "MANUAL_RECOVERY_REVIEW"
    assert "contact-secret@example.com" not in json.dumps(health)
    preview = recover_previous_private_checkpoint(
        tmp_path, as_of=NOW+timedelta(hours=1), test_only=True)
    assert preview["restored"] is False
    assert state_path.read_bytes() == corrupted
    restored = recover_previous_private_checkpoint(
        tmp_path, as_of=NOW+timedelta(hours=1), apply=True, test_only=True)
    assert restored["status"] == "PREVIOUS_GENERATION_RESTORED_EXPLICITLY"
    assert restored["restored"] is True
    assert restored["replay_source_window_required"] is True
    assert state_path.read_bytes() == original
    assert backup.read_bytes() == original
    evidence = list(state_path.parent.glob(state_path.name+".corrupt-*"))
    assert len(evidence) == 1
    assert evidence[0].read_bytes() == corrupted
    assert evidence[0].stat().st_mode & 0o777 == 0o600


def test_corrupt_active_refuses_new_checkpoint_and_preserves_previous_backup(tmp_path):
    from empire_os.uk_tender_incremental import _private_backup
    state_path = tmp_path/STAGE_PATH
    for at in (NOW,NOW+timedelta(hours=1)):
        advance_private_checkpoint(
            tmp_path, as_of=at, apply=True, test_only=True,
            fetch_page=lambda *args: page(rows=[]),
        )
    backup_path = _private_backup(state_path)
    before_backup = backup_path.read_bytes()
    state_path.write_bytes(b"not-json")
    with pytest.raises((TenderIncrementalHold,ValueError)):
        advance_private_checkpoint(
            tmp_path, as_of=NOW+timedelta(hours=2), apply=True, test_only=True,
            fetch_page=lambda *args: page(rows=[]),
        )
    assert state_path.read_bytes() == b"not-json"
    assert backup_path.read_bytes() == before_backup


def test_atomic_rename_failure_preserves_active_and_valid_previous(tmp_path,monkeypatch):
    import empire_os.uk_tender_incremental as module
    state_path = tmp_path/STAGE_PATH
    advance_private_checkpoint(tmp_path,as_of=NOW,apply=True,test_only=True,
                               fetch_page=lambda *args:page(rows=[]))
    first_bytes = state_path.read_bytes()
    original_writer = module._write_atomic_private
    calls = []
    def injected(target, encoded):
        calls.append(target)
        if target == state_path:
            raise OSError("simulated active checkpoint rename failure")
        return original_writer(target,encoded)
    monkeypatch.setattr(module,"_write_atomic_private",injected)
    with pytest.raises(OSError,match="simulated"):
        advance_private_checkpoint(
            tmp_path, as_of=NOW+timedelta(hours=1),apply=True,test_only=True,
            fetch_page=lambda *args:page(rows=[]),
        )
    assert state_path.read_bytes() == first_bytes
    assert module._private_backup(state_path).read_bytes() == first_bytes
    assert len(calls) == 2


def test_health_warns_of_receipt_capacity_before_history_hold(tmp_path):
    from empire_os.uk_tender_incremental import MAX_RECENT, review_incremental_checkpoint
    from hashlib import sha256
    checkpoint = empty_checkpoint()
    checkpoint["last_complete_window_end"] = NOW.strftime("%Y-%m-%dT%H:%M:%S")
    checkpoint["recent"] = {
        sha256(str(i).encode()).hexdigest(): {
            "semantic_digest": sha256(f"s{i}".encode()).hexdigest(),
            "ocid_digest": sha256(f"o{i}".encode()).hexdigest(),
        } for i in range(MAX_RECENT - MAX_RECENT//10)
    }
    path = tmp_path/STAGE_PATH
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(checkpoint))
    out = review_incremental_checkpoint(tmp_path,as_of=NOW)
    assert out["receipt_history_capacity_near_limit"] is True
    assert out["completed_receipt_slots_remaining"] == MAX_RECENT//10
    assert out["next_safe_operator_action"] == "REVIEW_SOURCE_RECEIPT_RETENTION"
    assert out["complete_source_coverage_claimed"] is False
