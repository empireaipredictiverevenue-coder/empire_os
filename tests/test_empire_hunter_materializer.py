from datetime import datetime, timezone
from uuid import uuid4

from empire_os.hunter.domain_intelligence import DomainIntelligenceReport
from empire_os.hunter.evidence_graph import build_evidence_plan
from empire_os.hunter.materializer import SupabaseHunterMaterializer
from empire_os.hunter.models import (
    ContactEvidence,
    DomainPattern,
    VerificationState,
)


def plan_fixture():
    contact = ContactEvidence(
        email="jane.smith@acme.com",
        state=VerificationState.CONFIRMED,
        confidence=0.96,
        source="first_party_schema_person",
        source_url="https://acme.com/team",
        person_name="Jane Smith",
        person_title="CEO",
        person_bound=True,
        first_party=True,
        syntax_ok=True,
        mx_ok=True,
    )
    report = DomainIntelligenceReport(
        requested_url="https://acme.com",
        domain="acme.com",
        business_names=("Acme",),
        contacts=(contact,),
        pattern=DomainPattern(
            domain="acme.com",
            pattern="first.last",
            observations=1,
            agreement=1.0,
            confidence=0.66,
        ),
        pages_checked=1,
        evidence_score=0.9,
    )
    return build_evidence_plan(
        report,
        entity_id=str(uuid4()),
        observed_at=datetime(
            2026, 9, 20, 14, 0, tzinfo=timezone.utc
        ),
    )


class FakeRequest:
    def __init__(self):
        self.calls = []

    def __call__(
        self,
        method,
        path,
        payload=None,
        *,
        prefer=None,
    ):
        self.calls.append(
            {
                "method": method,
                "path": path,
                "payload": payload,
                "prefer": prefer,
            }
        )
        if (
            method == "POST"
            and path.startswith("/rest/v1/intelligence_sources")
        ):
            return [{"id": "source-1"}]
        if (
            method == "GET"
            and path.startswith("/rest/v1/intelligence_employment")
        ):
            return []
        if (
            method == "GET"
            and path.startswith("/rest/v1/intelligence_people")
        ):
            return []
        if (
            method == "POST"
            and path == "/rest/v1/intelligence_people"
        ):
            return [{
                "id": "person-1",
                **payload,
            }]
        if (
            method == "POST"
            and path == "/rest/v1/intelligence_employment"
        ):
            return [{"id": "employment-1"}]
        if (
            method == "GET"
            and path.startswith(
                "/rest/v1/intelligence_contact_points"
            )
        ):
            return []
        if (
            method == "POST"
            and path == "/rest/v1/intelligence_contact_points"
        ):
            return [{"id": "contact-1"}]
        if (
            method == "POST"
            and path.startswith("/rest/v1/intelligence_facts")
        ):
            return [{"id": "fact-1"}]
        raise AssertionError((method, path, payload, prefer))


def test_observe_mode_never_calls_database():
    fake = FakeRequest()
    result = SupabaseHunterMaterializer(
        request_factory=fake
    ).materialize(
        plan_fixture(),
        write_authorized=False,
    )

    assert result["mode"] == "OBSERVE"
    assert result["write_authorized"] is False
    assert fake.calls == []


def test_materializer_writes_only_intelligence_fabric_tables():
    fake = FakeRequest()
    result = SupabaseHunterMaterializer(
        request_factory=fake
    ).materialize(
        plan_fixture(),
        write_authorized=True,
    )

    assert result["ok"] is True
    assert result["people_resolved"] == 1
    assert result["contacts_inserted"] == 1
    assert result["employments_written"] == 1
    assert result["facts_inserted"] == 1
    assert result["outbound_actions"] is False
    assert result["payment_actions"] is False
    assert result["revenue_actions"] is False

    paths = [call["path"] for call in fake.calls]
    assert all(
        "outbound" not in path
        and "payment" not in path
        and "commercial_events" not in path
        for path in paths
    )


def test_confirmed_contact_is_not_downgraded_by_probable_refresh():
    calls = []

    def request(
        method,
        path,
        payload=None,
        *,
        prefer=None,
    ):
        calls.append((method, path, payload, prefer))
        if method == "GET":
            return [{
                "id": "contact-1",
                "verification_state": "confirmed",
                "confidence": 0.96,
                "verified_at": "2026-09-19T10:00:00+00:00",
                "last_seen_at": "2026-09-19T10:00:00+00:00",
            }]
        if method == "PATCH":
            return [{"id": "contact-1", **payload}]
        raise AssertionError((method, path))

    materializer = SupabaseHunterMaterializer(
        request_factory=request
    )
    plan = plan_fixture()
    row = plan.contacts[0]
    probable_row = type(row)(
        person_normalized_name=row.person_normalized_name,
        entity_id=row.entity_id,
        contact_type=row.contact_type,
        value=row.value,
        normalized_value=row.normalized_value,
        verification_state="probable",
        confidence=0.70,
        first_seen_at=row.first_seen_at,
        last_seen_at=row.last_seen_at,
        verified_at=None,
        evidence_uri=row.evidence_uri,
    )

    _, action = materializer._contact(
        source_id="source-1",
        person_id="person-1",
        row=probable_row,
        observed_at=plan.observed_at,
    )

    assert action == "updated"
    patch = next(
        call for call in calls
        if call[0] == "PATCH"
    )
    assert patch[2]["verification_state"] == "confirmed"
    assert patch[2]["confidence"] == 0.96
