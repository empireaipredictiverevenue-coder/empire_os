from datetime import datetime, timedelta, timezone
import json

from empire_os.buyer_claim_provenance import classify_buyer_source_pages
from empire_os.buyer_evidence_quality_scorecard import (
    build_evidence_quality_scorecard,
    refresh_evidence_quality_scorecard,
)


NOW = datetime(2026, 10, 9, 16, 5, tzinfo=timezone.utc)
STAMP = NOW.isoformat()


def evidence(website="https://buyer.example", text="We buy leads from publishers."):
    return classify_buyer_source_pages(
        [{"url": website + "/partners", "visible_text": text}],
        company_website=website, observed_at=STAMP,
    )


def payloads():
    good = {
        "domain": "buyer.example", "website": "https://buyer.example",
        "explicit_direct_buyer_evidence": True,
        "buyer_relationship": "direct_inventory_buyer",
        "buyer_claim_provenance": evidence(),
        "first_party_people": [{
            "name": "Jane Smith", "title": "Head of Growth",
            "email": "jane@buyer.example", "url": "https://buyer.example/team/jane",
            "direct_publication": True,
        }],
        "first_party_emails": ["jane@buyer.example"],
        "commercial_sitemap_candidate_count": 2,
        "commercial_sitemap_page_fetch_count": 1,
    }
    suspect = {
        "domain": "vendor.example", "website": "https://vendor.example",
        "explicit_direct_buyer_evidence": True,
        "buyer_relationship": "direct_inventory_buyer",
        "buyer_claim_provenance": None,
        "first_party_people": [{"name": "Lee Chen", "title": "Director"}],
        "first_party_emails": ["info@vendor.example"],
    }
    scout = {"generated_at": STAMP, "candidates": [good, suspect]}
    reconciliation = {"generated_at": STAMP, "candidate_count": 2}
    persistence = {"generated_at": STAMP, "persisted_candidate_count": 1}
    review = {
        "generated_at": STAMP, "candidate_count": 198, "review_ready_count": 1,
        "blocked_reason_counts": {"direct_buyer_evidence_missing": 43},
    }
    return scout, reconciliation, persistence, review


def test_scorecard_separates_direct_proof_and_contact_observations():
    out = build_evidence_quality_scorecard(*payloads(), now=NOW)
    assert out["scout_receipt_fresh"] is True
    assert out["stage_receipts_time_aligned"] is True
    assert out["scout_candidate_count"] == 2
    assert out["candidate_with_valid_direct_purchase_receipt"] == 1
    assert out["candidate_with_sitemap_commercial_page"] == 1
    assert out["commercial_sitemap_pages_fetched"] == 1
    assert out["unsupported_positive_direct_buyer_flags"] == 1
    assert out["candidate_with_named_person_record"] == 2
    assert out["candidate_with_published_company_email"] == 2
    assert out["candidate_with_strict_named_person_email_binding"] == 1
    assert out["pending_holding_review_evaluated"] == 198
    assert out["pending_holding_new_review_transitions"] == 1
    assert out["scout_to_pending_holding_conversion_rate"] is None
    assert out["database_write_performed"] is False
    assert out["outbound_sent"] is False


def test_mismatched_and_undated_snapshots_not_mixed_as_cohort():
    scout, reconciliation, persistence, review = payloads()
    scout["generated_at"] = (NOW - timedelta(hours=2)).isoformat()
    out = build_evidence_quality_scorecard(
        scout, reconciliation, persistence, review, now=NOW,
    )
    assert out["scout_receipt_fresh"] is False
    assert out["stage_receipts_time_aligned"] is False
    review["generated_at"] = None
    out = build_evidence_quality_scorecard(
        scout, reconciliation, persistence, review, now=NOW,
    )
    assert out["stage_receipts_time_aligned"] is False


def test_published_email_without_binding_is_not_verified():
    scout, reconciliation, persistence, review = payloads()
    person = scout["candidates"][0]["first_party_people"][0]
    person.pop("direct_publication")
    out = build_evidence_quality_scorecard(
        scout, reconciliation, persistence, review, now=NOW,
    )
    assert out["candidate_with_published_company_email"] == 2
    assert out["candidate_with_strict_named_person_email_binding"] == 0


def test_write_aggregate_receipt_without_changing_source_inputs(tmp_path):
    scout, reconciliation, persistence, review = payloads()
    values = (scout, reconciliation, persistence, review)
    folder = tmp_path / "runtime" / "buyer_acquisition"
    folder.mkdir(parents=True)
    filenames = [
        "scout_latest.json", "reconciliation_latest.json",
        "persistence_latest.json", "review_readiness_latest.json",
    ]
    for name, data in zip(filenames, values):
        (folder / name).write_text(json.dumps(data))
    outputs = refresh_evidence_quality_scorecard(tmp_path)
    path = folder / "evidence_quality_latest.json"
    assert path.exists()
    actual = json.loads(path.read_text())
    assert actual == outputs
    assert actual["mode"] == "OBSERVE"
    for name, data in zip(filenames, values):
        assert json.loads((folder / name).read_text()) == data


def test_failed_source_parse_does_not_write_misleading_receipt(tmp_path):
    folder = tmp_path / "runtime" / "buyer_acquisition"
    folder.mkdir(parents=True)
    (folder / "scout_latest.json").write_text("unparseable")
    try:
        refresh_evidence_quality_scorecard(tmp_path)
    except json.JSONDecodeError:
        pass
    else:
        raise AssertionError("expected invalid source to fail")
    assert not (folder / "evidence_quality_latest.json").exists()
