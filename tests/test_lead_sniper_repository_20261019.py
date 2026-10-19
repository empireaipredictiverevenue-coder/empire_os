"""EmpireDB canonical Lead Sniper review endpoint, no outbound or Supabase."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from empire_os.data_cloud_contract import DataBackend
from empire_os.data_query import FilterOperator
from empire_os.lead_sniper_repository import (
    LeadSniperRepository, review_b2b_sniper_candidate, SCHEMA,
)

NOW = datetime(2026, 10, 19, 12, 50, tzinfo=timezone.utc)
URL = "https://example-business.co.uk/contact"


class FakeGateway:
    def __init__(self, *, backend=DataBackend.EMPIREDB, configured=True):
        self.backend = backend
        self.configured = configured
        self.queries = []
        self.inserts = []
        self.rows = []

    def query(self, table, columns, *, filters=(), limit=0, **kwargs):
        self.queries.append((table, columns, filters, limit))
        assert table == "empire_tasks"
        return list(self.rows)

    def insert(self, table, payload, *, return_repr=False):
        self.inserts.append((table, payload, return_repr))
        self.rows = [{
            "id": "synthetic-db-task", "payload": payload["payload"],
            "created_at": NOW.isoformat(),
        }]
        return []


def business(**kwargs):
    source = {
        "business_name": "Acme Solar Systems Ltd",
        "source": "gb_recc_solar",
        "registered_source_id": "gb_recc_solar",
        "registered_source_evidence_url": "https://www.recc.org.uk/scheme/members",
        "source_rights_receipt_ref": "approved:source-use-20261019",
        "canonical_business_identity_ref": "business:verified-company-321",
        "source_territory_ref": "verified-territory:GB-ENG-221",
        "territory_code": "GB-ENG",
        "outreach_authorized": False,
        "contains_consumer_claimant_or_patient_data": False,
        "entity_kind": "company",
        "details": {"url": URL, "observed_at": NOW.isoformat()},
    }
    source.update(kwargs)
    return source


def approved():
    return review_b2b_sniper_candidate(business(), "solar", 0.87, now=NOW)


def test_registered_b2b_firm_is_review_proposal_only():
    p = approved()
    assert p["decision"] == "B2B_REVIEW_PROPOSAL"
    assert p["reasons"] == []
    assert p["source"] == "gb_recc_solar"
    assert p["buyer_intent_verified"] is False
    assert p["outreach_authorized"] is False
    assert p["canonical_prospect_promotion_authorized"] is False


@pytest.mark.parametrize("overrides", [
    {"business_name": None},
    {"entity_kind": "person"},
    {"contains_consumer_claimant_or_patient_data": None},
    {"contains_consumer_claimant_or_patient_data": True},
    {"source_rights_receipt_ref": ""},
    {"canonical_business_identity_ref": ""},
    {"source_territory_ref": ""},
    {"outreach_authorized": None},
    {"outreach_authorized": True},
    {"territory_code": "US-TX"},
    {"registered_source_evidence_url": "https://bad-example.invalid/recc"},
    {"source": "reddit:r/HomeImprovement", "registered_source_id": "reddit:r/HomeImprovement"},
    {"registered_source_id": "gb_find_a_tender_ocds"},
    {"details": {"url": "http://example-business.co.uk/contact",
                 "observed_at": NOW.isoformat()}},
    {"details": {"url": "https://127.0.0.1/",
                 "observed_at": NOW.isoformat()}},
])
def test_legacy_consumer_incomplete_or_unlicensed_fails_closed(overrides):
    r = review_b2b_sniper_candidate(business(**overrides), "solar", 0.9, now=NOW)
    assert r["decision"] == "HOLD"
    assert r["reasons"]
    assert r["outreach_authorized"] is False


def test_old_reddit_scope_with_high_score_not_b2b_identity():
    legacy = {
        "name": "private Reddit author",
        "niche": "roofing", "source": "reddit:r/Roofing",
        "details": {"url": "https://reddit.com/r/Roofing/post/7",
                    "title": "Need a roofer today", "age_hours": 1}
    }
    result = review_b2b_sniper_candidate(legacy, "roofing", 1.0, now=NOW)
    assert result["decision"] == "HOLD"
    assert "registered_identity_source_and_rights_required" in result["reasons"]
    assert "b2b_entity_classification_not_proven" in result["reasons"]


@pytest.mark.parametrize("niche,kind", [
    ("mass_torts", "law_firm"), ("insurance", "insurance_broker"),
    ("dental", "medical_practice"), ("legal", "law_firm"),
])
def test_regulated_verticals_require_special_review(niche, kind):
    result = review_b2b_sniper_candidate(
        business(entity_kind="company"), niche, 0.9, now=NOW
    )
    assert "regulated_b2b_jurisdiction_review_required" in result["reasons"]


def test_canonical_backend_enforced_no_supabase_fallback():
    store = LeadSniperRepository(FakeGateway(backend=DataBackend.SUPABASE_LEGACY))
    with pytest.raises(RuntimeError, match="canonical_primary_must_be_empiredb"):
        store.pending_review_exists(URL, now=NOW)


def test_canonical_reader_filters_task_type_and_url_across_all_review_statuses():
    gateway = FakeGateway()
    store = LeadSniperRepository(gateway)
    assert not store.pending_review_exists(URL, now=NOW)
    table, columns, filters, limit = gateway.queries[0]
    assert table == "empire_tasks"
    assert columns == "id,payload,created_at"
    assert [f.column for f in filters] == [
        "task_type", "payload->>url"
    ]
    assert all(f.operator is FilterOperator.EQ for f in filters)
    assert limit == 2


def test_review_writes_disabled_by_default_even_good_receipt():
    gateway = FakeGateway()
    repo = LeadSniperRepository(gateway)
    result = repo.queue_review(approved(), now=NOW)
    assert result["status"] == "held"
    assert result["reason"] == "canonical_review_queue_not_activated"
    assert gateway.queries == []
    assert gateway.inserts == []


def test_held_candidate_cannot_be_written_even_with_writes_on():
    gateway = FakeGateway()
    repo = LeadSniperRepository(gateway, queue_enabled=True)
    hold = review_b2b_sniper_candidate(business(entity_kind="person"), "solar", 0.99, now=NOW)
    assert repo.queue_review(hold, now=NOW)["status"] == "held"
    assert gateway.inserts == []


def test_exact_dedup_prevents_duplicate_and_readback_proves_write():
    gateway = FakeGateway()
    repo = LeadSniperRepository(gateway, queue_enabled=True)
    result = repo.queue_review(approved(), now=NOW)
    assert result == {
        "ok": True, "status": "review_queued", "canonical_write_performed": True
    }
    assert len(gateway.inserts) == 1
    table, payload, return_repr = gateway.inserts[0]
    assert table == "empire_tasks"
    assert return_repr is False
    assert payload["task_type"] == "sniper_review"
    assert payload["status"] == "pending"
    assert payload["payload"]["outbound_authorized"] is False
    assert payload["payload"]["schema_version"] == SCHEMA
    assert repo.queue_review(approved(), now=NOW)["status"] == "deduped"
    assert len(gateway.inserts) == 1


def test_nonmatching_rows_and_two_results_fail_closed():
    gateway = FakeGateway()
    repo = LeadSniperRepository(gateway)
    gateway.rows = [
        {"payload": {"url": "https://unrelated.example/contact"},
         "created_at": NOW.isoformat()}
    ]
    with pytest.raises(RuntimeError, match="inconsistent"):
        repo.pending_review_exists(URL, now=NOW)
    gateway.rows *= 2
    with pytest.raises(RuntimeError, match="need_manual_reconciliation"):
        repo.pending_review_exists(URL, now=NOW)


def test_unreadable_timestamp_blocks_duplicate_insert():
    gateway = FakeGateway()
    repo = LeadSniperRepository(gateway, queue_enabled=True)
    gateway.rows = [{"payload": {"url": URL}, "created_at": "invalid"}]
    with pytest.raises(RuntimeError, match="timestamp_missing"):
        repo.queue_review(approved(), now=NOW)
    assert gateway.inserts == []


def test_unconfirmed_write_not_claimed():
    gateway = FakeGateway()
    def missing_record(*args, **kwargs):
        gateway.inserts.append("attempt")
        return []
    gateway.insert = missing_record
    repo = LeadSniperRepository(gateway, queue_enabled=True)
    with pytest.raises(RuntimeError, match="write_not_confirmed"):
        repo.queue_review(approved(), now=NOW)
    assert len(gateway.inserts) == 1


def test_partial_hours_budget():
    repo = LeadSniperRepository(FakeGateway())
    with pytest.raises(ValueError, match="invalid_dedup_window"):
        repo.pending_review_exists(URL, dedup_hours=0, now=NOW)


def test_research_age_and_score_gate():
    old = business(details={"url": URL, "observed_at": (NOW - timedelta(days=8)).isoformat()})
    assert review_b2b_sniper_candidate(old, "solar", 0.87, now=NOW)["decision"] == "HOLD"
    assert review_b2b_sniper_candidate(business(), "solar", 0.2, now=NOW)["decision"] == "HOLD"
