"""Proof that the actual LEGACY sniper now routes to EmpireDB gate safely."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest

from empire_os.agents import lead_sniper_agent as sniper
from empire_os.data_cloud_contract import DataBackend
from empire_os.lead_sniper_repository import LeadSniperRepository


class FakeGateway:
    backend = DataBackend.EMPIREDB
    configured = True

    def __init__(self):
        self.queries = 0
        self.inserts = []
        self.rows = []

    def query(self, table, columns="*", *, filters=(), limit=2, **kwargs):
        self.queries += 1
        return list(self.rows)

    def insert(self, table, row, *, return_repr=False):
        self.inserts.append((table, row))
        self.rows = [{
            "id": "synthetic-research-task",
            "payload": row["payload"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }]
        return []


def approved_b2b():
    return {
        "business_name": "Example Solar Engineering Ltd",
        "entity_kind": "company",
        "contains_consumer_claimant_or_patient_data": False,
        "source": "gb_recc_solar",
        "registered_source_id": "gb_recc_solar",
        "registered_source_evidence_url": "https://www.recc.org.uk/scheme/members",
        "canonical_business_identity_ref": "company:verified-enterprise-001",
        "source_rights_receipt_ref": "governance:source-reviewed-001",
        "source_territory_ref": "territory:GB-ENG-company-001",
        "territory_code": "GB-ENG",
        "outreach_authorized": False,
        "details": {
            "url": "https://example-solar.co.uk/contact",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "title": "New B2B solar project needs installation",
        },
    }


def test_legacy_agent_now_uses_canonical_adapter_with_disabled_writes():
    gateway = FakeGateway()
    held = sniper._queue_review(
        approved_b2b(), "solar", 0.85,
        repository=LeadSniperRepository(gateway, queue_enabled=False),
    )
    assert held["status"] == "held"
    assert held["reason"] == "canonical_review_queue_not_activated"
    assert gateway.inserts == []


def test_explicit_enabled_adapter_produces_canonical_review_only():
    gateway = FakeGateway()
    out = sniper._queue_review(
        approved_b2b(), "solar", 0.85,
        repository=LeadSniperRepository(gateway, queue_enabled=True),
    )
    assert out["status"] == "review_queued"
    assert gateway.inserts[0][0] == "empire_tasks"
    row = gateway.inserts[0][1]
    assert row["task_type"] == "sniper_review"
    assert row["status"] == "pending"
    assert row["payload"]["outbound_authorized"] is False
    assert row["payload"]["canonical_prospect_promotion_authorized"] is False


def test_reddit_urgency_cannot_contact_or_queue_a_person():
    gateway = FakeGateway()
    lead = {
        "source": "reddit:r/Roofing", "name": "anonymous",
        "details": {"title": "Need a roofer right now",
                    "url": "https://www.reddit.com/r/Roofing/comments/x",
                    "age_hours": 2},
    }
    out = sniper._queue_review(
        lead, "roofing", 1.0,
        repository=LeadSniperRepository(gateway, queue_enabled=True),
    )
    assert out["status"] == "held"
    assert "registered_identity_source_and_rights_required" in out["reasons"]
    assert gateway.queries == 0
    assert gateway.inserts == []


def test_canonical_read_failure_is_dedup_hold():
    class UnavailableRepository:
        def pending_review_exists(self, *a, **k):
            raise ConnectionError("private credential should not be logged")
    assert sniper._already_reviewed(
        "https://firm.example/contact", repository=UnavailableRepository()
    ) is True


def test_legacy_scopes_do_not_make_http_requests_by_default(monkeypatch):
    monkeypatch.delenv("EMPIRE_SNIPER_LEGACY_PUBLIC_FETCH_APPROVED", raising=False)
    import urllib.request
    monkeypatch.setattr(
        urllib.request, "urlopen",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("network source must not be called")
        ),
    )
    assert sniper.RedditUrgentScope().scan("roofing") == []
    assert sniper.CountyPermitsUrgentScope().scan("roofing") == []


def test_legacy_sniper_agent_source_has_no_supabase_dependency():
    source = Path(sniper.__file__).read_text()
    assert "import empire_os.sb" not in source
    assert "sb.select" not in source
    assert "sb.insert" not in source
    assert 'sys.path.insert(0, "/root/empire_os")' not in source
    assert "LeadSniperRepository" in source
    assert "SNIPER_FEEDBACK_DIR" in source
