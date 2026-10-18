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
    assert finished["last_complete_window_end"] == (NOW - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S")


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
