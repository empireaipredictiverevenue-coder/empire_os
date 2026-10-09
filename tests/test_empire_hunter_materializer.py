from datetime import datetime, timezone
from uuid import uuid4
from copy import deepcopy
from urllib.parse import parse_qs, urlsplit

import pytest

from empire_os.hunter.domain_intelligence import DomainIntelligenceReport
from empire_os.hunter.evidence_graph import build_evidence_plan
from empire_os.hunter.materializer import HunterMaterializerError, SupabaseHunterMaterializer
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
        self.facts = []

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
        if urlsplit(path).path == "/rest/v1/intelligence_facts":
            params = parse_qs(urlsplit(path).query)
            if method == "GET":
                assert params["select"] == ["entity_id,fact_key,source_id,evidence_hash"]
                assert params["limit"] == ["2"]
                return deepcopy([row for row in self.facts
                                 if "eq." + row["evidence_hash"] == params["evidence_hash"][0]][:2])
            assert method == "POST"
            assert "on_conflict" not in params
            assert prefer == "resolution=ignore-duplicates,return=representation"
            if any(row["evidence_hash"] == payload["evidence_hash"] for row in self.facts):
                return []
            row = {"id": str(uuid4()), **deepcopy(payload)}
            self.facts.append(row)
            return [deepcopy(row)]
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
    assert patch[2]["verification_state"] == "verified"
    assert patch[2]["confidence"] == 0.96

def test_fact_replay_reuses_without_insert_or_mutation():
    fake = FakeRequest()
    writer = SupabaseHunterMaterializer(request_factory=fake)
    plan = plan_fixture()
    assert writer.materialize(plan, write_authorized=True)["facts_inserted"] == 1
    before = deepcopy(fake.facts)
    fake.calls.clear()
    assert writer.materialize(plan, write_authorized=True)["facts_inserted"] == 0
    assert fake.facts == before
    assert not any(call["method"] != "GET" and "intelligence_facts" in call["path"]
                   for call in fake.calls)
    assert fake("POST", "/rest/v1/intelligence_facts", payload=before[0],
                prefer="resolution=ignore-duplicates,return=representation") == []
    assert fake.facts == before


@pytest.mark.parametrize("field", ["entity_id", "fact_key", "source_id", "evidence_hash"])
def test_fact_conflicting_existing_row_fails_closed(field):
    fake = FakeRequest()
    plan = plan_fixture()
    SupabaseHunterMaterializer(request_factory=fake)._facts(source_id="source-1", plan=plan)
    row = deepcopy(fake.facts[0])
    row[field] = "conflicting"
    calls = []
    def request(method, path, **kwargs):
        calls.append(method)
        return [row]
    with pytest.raises(HunterMaterializerError):
        SupabaseHunterMaterializer(request_factory=request)._facts(source_id="source-1", plan=plan)
    assert calls == ["GET"]


@pytest.mark.parametrize("canonical", ["compatible", "missing", "conflicting", "multiple"])
def test_fact_zero_row_insert_requires_compatible_canonical_reread(canonical):
    fake = FakeRequest()
    plan = plan_fixture()
    def raced(method, path, **kwargs):
        if method == "POST":
            rows = fake(method, path, **kwargs)
            if canonical == "missing":
                fake.facts.clear()
            elif canonical == "conflicting":
                fake.facts[0]["source_id"] = "another-source"
            elif canonical == "multiple":
                fake.facts.append(deepcopy(rows[0]))
            return []
        return fake(method, path, **kwargs)
    writer = SupabaseHunterMaterializer(request_factory=raced)
    if canonical == "compatible":
        assert writer._facts(source_id="source-1", plan=plan) == 0
        assert len(fake.facts) == 1
    else:
        with pytest.raises(HunterMaterializerError):
            writer._facts(source_id="source-1", plan=plan)
    assert [call["method"] for call in fake.calls] == ["GET", "POST", "GET"]


def test_multiple_existing_facts_fail_without_write():
    fake = FakeRequest()
    writer = SupabaseHunterMaterializer(request_factory=fake)
    plan = plan_fixture()
    writer._facts(source_id="source-1", plan=plan)
    fake.facts.append(deepcopy(fake.facts[0]))
    fake.calls.clear()
    with pytest.raises(HunterMaterializerError):
        writer._facts(source_id="source-1", plan=plan)
    assert [call["method"] for call in fake.calls] == ["GET"]
