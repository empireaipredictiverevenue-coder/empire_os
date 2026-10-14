"""First-party canonical CRM JEV snapshot stays read-only and honest."""
from datetime import datetime, timezone
from uuid import UUID
import pytest

from empire_os.jev_gtm_crm_review import read_jev_crm_review
from empire_os.revenue_crm_transport import (
    PostgresRevenueCrmRepository, RevenueCrmTransportError,
    PROSPECT_COLUMNS, PROSPECT_LIST_SQL,
)

NOW = datetime(2026, 10, 14, 9, tzinfo=timezone.utc)
TENANT, OTHER = str(UUID(int=1)), str(UUID(int=99))
PROSPECT, SECOND = str(UUID(int=2)), str(UUID(int=3))
COLS = PROSPECT_COLUMNS.split(",")


def row(*, prospect=PROSPECT, tenant=TENANT, conversation=None, closer=None):
    data = dict.fromkeys(COLS)
    data.update({
        "tenant_id": tenant, "prospect_id": prospect,
        "business_name": "Fictional Roofing",
        "niche": "roofing", "metro": "Manchester",
        "prospect_status": "qualified",
        "conversation_id": conversation,
        "conversation_state": "engaged" if conversation else None,
        "closer_case_id": closer,
        "closer_state": "proposal_ready" if closer else None,
    })
    return tuple(data[c] for c in COLS)


class Column:
    def __init__(self, name):
        self.name = name


class FakeCursor:
    def __init__(self, rows, *, bound_tenant=TENANT):
        self.rows = rows
        self.bound_tenant = bound_tenant
        self.description = [Column(c) for c in COLS]
        self.calls = []

    def __enter__(self): return self
    def __exit__(self, *args): return False

    def execute(self, sql, values=None):
        self.calls.append((sql, values))

    def fetchone(self):
        return (self.bound_tenant,)

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_instance = cursor

    def __enter__(self): return self
    def __exit__(self, *args): return False

    def cursor(self):
        return self.cursor_instance


def repository(rows=None, bound_tenant=TENANT):
    cur = FakeCursor(rows if rows is not None else [row()], bound_tenant=bound_tenant)
    repo = PostgresRevenueCrmRepository(
        "fake-test-dsn", tenant_id=TENANT,
        connect_factory=lambda _: FakeConnection(cur),
    )
    return repo, cur


def test_canonical_prospect_is_research_not_buyer_reply():
    repo, cur = repository()
    summary = read_jev_crm_review(repo, as_of=NOW)
    assert summary["scanned_count"] == 1
    assert summary["research_lanes"] == {"CANONICAL_IDENTITY_RESEARCH": 1}
    item = summary["items"][0]
    assert item["prospect_id"] == PROSPECT
    assert item["buyer_identity_verified"] is False
    assert item["original_inbound_event_verified"] is False
    assert item["suppression_clearance_verified"] is False
    assert item["outbound_approved"] is False
    assert summary["original_provider_reply_count_verified"] is None
    assert summary["recognized_revenue"] is None
    assert cur.calls[0][0] == "SET TRANSACTION READ ONLY"
    assert cur.calls[-1] == (PROSPECT_LIST_SQL, (TENANT, 50))


def test_no_customer_personal_information_in_summary():
    repo, _ = repository()
    result = read_jev_crm_review(repo, as_of=NOW)
    assert "business_name" not in result["items"][0]
    assert "email" not in str(result)
    assert "Fictional Roofing" not in str(result)


def test_empty_rows_do_not_prove_no_company_in_database():
    repo, _ = repository([])
    result = read_jev_crm_review(repo, as_of=NOW)
    assert result["scanned_count"] == 0
    assert result["complete_tenant_inventory_verified"] is False
    assert result["commercial_buyer_count_verified"] is None
    assert result["more_rows_possible"] is False


def test_exact_limit_does_not_claim_pagination_complete():
    repo, _ = repository([row(), row(prospect=SECOND)])
    result = read_jev_crm_review(repo, as_of=NOW, limit=2)
    assert result["more_rows_possible"] is True
    assert result["complete_tenant_inventory_verified"] is False


def test_optional_conversation_reference_does_not_verify_reply():
    repo, _ = repository([row(conversation=str(UUID(int=5)))])
    result = read_jev_crm_review(repo, as_of=NOW)
    item = result["items"][0]
    assert item["research_lane"] == "REPLY_EVIDENCE_REVIEW"
    assert item["conversation_original_proof_verified"] is False
    assert item["original_inbound_event_verified"] is False
    assert "ORIGINAL_INBOUND_PROVIDER_AND_TENANT_PROOF_PENDING" in item["qualification_blockers"]
    assert "CANONICAL_CONTACT_BINDING_NOT_VERIFIED" in item["qualification_blockers"]


def test_existing_deterministic_action_is_never_an_approved_outbound():
    repo, _ = repository([row(closer=str(UUID(int=7)))])
    result = read_jev_crm_review(repo, as_of=NOW)
    assert result["items"][0]["deterministic_crm_action_candidate"] == "review_proposal_readiness"
    assert result["items"][0]["outbound_approved"] is False
    assert result["execution_authority"] == "none"


def test_scope_rejection_by_existing_reader():
    repo, _ = repository([row(tenant=OTHER)])
    with pytest.raises(RevenueCrmTransportError):
        read_jev_crm_review(repo, as_of=NOW)


def test_wrong_session_binding_rejected_before_sql():
    repo, cur = repository(bound_tenant=OTHER)
    with pytest.raises(RevenueCrmTransportError):
        read_jev_crm_review(repo, as_of=NOW)
    assert all(sql != PROSPECT_LIST_SQL for sql, _ in cur.calls)


def test_duplicate_canonical_id_is_rejected():
    repo, _ = repository([row(), row()])
    with pytest.raises(ValueError, match="duplicate"):
        read_jev_crm_review(repo, as_of=NOW)


def test_client_supplied_fake_repository_rejected():
    class Rogue:
        tenant_id = TENANT
        def prospects(self, *, limit):
            return [dict(tenant_id=TENANT, prospect_id=PROSPECT)]

    with pytest.raises(ValueError, match="dedicated"):
        read_jev_crm_review(Rogue(), as_of=NOW)


@pytest.mark.parametrize("limit", [0, -1, 101, 1.1, True, "3"])
def test_bounded_review_limit(limit):
    repo, _ = repository()
    with pytest.raises(ValueError, match="bounded"):
        read_jev_crm_review(repo, limit=limit, as_of=NOW)


def test_stable_fingerprint_and_tenant_privacy():
    repo, _ = repository()
    a = read_jev_crm_review(repo, as_of=NOW)
    b = read_jev_crm_review(repo, as_of=NOW)
    assert a["review_fingerprint"] == b["review_fingerprint"]
    assert "tenant_id" not in a
    assert a["contact_permission_granted"] is False
