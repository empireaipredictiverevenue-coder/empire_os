"""JEV reply candidates require exact tenant/prospect and do not become verified buyers."""
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from empire_os.revenue_crm_transport import PostgresRevenueCrmRepository, RevenueCrmTransportError
from empire_os.jev_gtm_reply_candidate_reader import RPC_SQL, review_jev_reply_candidates

NOW = datetime(2026, 10, 14, 9, tzinfo=timezone.utc)
TENANT, PROSPECT, REPLY, INTENT, OTHER = [str(UUID(int=n)) for n in range(1, 6)]
COLS = (
    "tenant_id", "prospect_id", "reply_id", "outbound_intent_id", "received_at",
    "reply_classification", "intent_status", "provider_reference_present",
    "matching_conversation_count", "original_provider_authenticated",
    "contact_binding_verified",
)


def row(**kw):
    value = {
        "tenant_id": TENANT, "prospect_id": PROSPECT, "reply_id": REPLY,
        "outbound_intent_id": INTENT, "received_at": NOW - timedelta(hours=2),
        "reply_classification": "positive", "intent_status": "replied",
        "provider_reference_present": True, "matching_conversation_count": 1,
        "original_provider_authenticated": False,
        "contact_binding_verified": False,
    }
    value.update(kw)
    return tuple(value.get(c) for c in COLS)


class Field:
    def __init__(self, name): self.name = name


class Cursor:
    def __init__(self, rows, tenant=TENANT, failure=None):
        self.rows = rows
        self.tenant = tenant
        self.failure = failure
        self.calls = []
        self.description = [Field(c) for c in COLS]

    def __enter__(self): return self
    def __exit__(self, *args): return False
    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        if self.failure is not None and "empire_read_crm_reply_candidates" in sql:
            raise self.failure
    def fetchone(self): return (self.tenant,)
    def fetchall(self): return self.rows


class Connection:
    def __init__(self, cursor): self.cur = cursor
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def cursor(self): return self.cur


def setup(rows=None, *, tenant=TENANT, failure=None):
    cursor = Cursor([row()] if rows is None else rows, tenant=tenant, failure=failure)
    repository = PostgresRevenueCrmRepository(
        "fake-test-only", tenant_id=TENANT,
        connect_factory=lambda dsn: Connection(cursor),
    )
    return repository, cursor


def test_reply_candidate_uses_only_authenticated_existing_crm_transport():
    repo, cur = setup()
    review = review_jev_reply_candidates(repo, prospect_id=PROSPECT, as_of=NOW)
    assert cur.calls[0][0] == "SET TRANSACTION READ ONLY"
    assert cur.calls[1][0] == "SET LOCAL ROLE empire_revenue_crm_reader"
    assert cur.calls[-1] == (RPC_SQL, (PROSPECT, 25))
    assert review["candidate_count"] == 1
    assert review["candidate_counts_by_unverified_class"]["positive"] == 1
    assert review["genuine_buying_conversations_verified"] is None
    assert review["original_provider_authenticated_count"] is None
    assert review["recognized_revenue"] is None
    assert review["send_authorized"] is False
    assert review["items"][0]["positive_buyer_reply_verified"] is False
    assert review["items"][0]["blocker"] == "ORIGINAL_PROVIDER_AND_CONTACT_PROOF_PENDING"


def test_zero_candidates_does_not_prove_no_inbox_replies():
    repo, _ = setup([])
    result = review_jev_reply_candidates(repo, prospect_id=PROSPECT, as_of=NOW)
    assert result["candidate_count"] == 0
    assert result["full_tenant_inbox_verified"] is False
    assert result["original_provider_authenticated_count"] is None


@pytest.mark.parametrize("field,value", [
    ("tenant_id", OTHER),
    ("prospect_id", OTHER),
    ("reply_id", "invalid"),
    ("outbound_intent_id", "invalid"),
    ("received_at", NOW + timedelta(seconds=5)),
    ("received_at", "not-a-date"),
    ("reply_classification", "send_now"),
    ("original_provider_authenticated", True),
    ("contact_binding_verified", True),
    ("matching_conversation_count", -1),
    ("provider_reference_present", "yes"),
])
def test_wrong_scope_or_tampered_attestation_fails_closed(field, value):
    repo, _ = setup([row(**{field: value})])
    with pytest.raises(RevenueCrmTransportError if field == "tenant_id" else ValueError):
        review_jev_reply_candidates(repo, prospect_id=PROSPECT, as_of=NOW)


@pytest.mark.parametrize("match,provider,reason", [
    (0, True, "CONVERSATION_CARDINALITY_UNPROVEN"),
    (2, True, "CONVERSATION_CARDINALITY_UNPROVEN"),
    (1, False, "ORIGINAL_PROVIDER_MESSAGE_REFERENCE_MISSING"),
])
def test_duplicate_missing_or_unlinked_conversation_not_promoted(match,provider,reason):
    repo, _ = setup([row(matching_conversation_count=match, provider_reference_present=provider)])
    result = review_jev_reply_candidates(repo, prospect_id=PROSPECT, as_of=NOW)
    assert result["items"][0]["blocker"] == reason
    assert result["items"][0]["positive_buyer_reply_verified"] is False


def test_duplicate_reply_ids_rejected():
    repo, _ = setup([row(), row()])
    with pytest.raises(ValueError, match="duplicated"):
        review_jev_reply_candidates(repo, prospect_id=PROSPECT, as_of=NOW)


def test_wrong_authenticated_session_fails_before_source_rpc():
    repo, cur = setup(tenant=OTHER)
    with pytest.raises(RevenueCrmTransportError):
        review_jev_reply_candidates(repo, prospect_id=PROSPECT, as_of=NOW)
    assert not any("empire_read_crm_reply_candidates" in sql for sql, _ in cur.calls)


def test_unavailable_migration_fails_closed_with_sanitized_error():
    repo, _ = setup(failure=RuntimeError("permission denied PRIVATE DSN"))
    with pytest.raises(RevenueCrmTransportError) as exc:
        review_jev_reply_candidates(repo, prospect_id=PROSPECT, as_of=NOW)
    assert "PRIVATE" not in str(exc.value)


@pytest.mark.parametrize("limit", [0, 101, True, -1, "5", 2.5])
def test_bounds_before_database_access(limit):
    repo, cur = setup()
    with pytest.raises(ValueError, match="bounded"):
        review_jev_reply_candidates(repo, prospect_id=PROSPECT, limit=limit, as_of=NOW)
    assert cur.calls == []


def test_original_source_cannot_invent_raw_body_or_contact_fields():
    repo, _ = setup()
    result = review_jev_reply_candidates(repo, prospect_id=PROSPECT, as_of=NOW)
    assert "body_text" not in repr(result)
    assert "from_contact" not in repr(result)
    assert "normalized_from_contact" not in repr(result)


def test_replay_is_deterministic_with_no_side_effects():
    repo, _ = setup()
    first = review_jev_reply_candidates(repo, prospect_id=PROSPECT, as_of=NOW)
    second = review_jev_reply_candidates(repo, prospect_id=PROSPECT, as_of=NOW)
    assert first == second
    assert first["execution_authority"] == "none"
