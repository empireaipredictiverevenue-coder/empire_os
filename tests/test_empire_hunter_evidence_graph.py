from datetime import datetime, timezone
from uuid import uuid4

from empire_os.hunter.domain_intelligence import DomainIntelligenceReport
from empire_os.hunter.evidence_graph import (
    build_evidence_plan,
    evidence_hash,
)
from empire_os.hunter.models import (
    ContactEvidence,
    DomainPattern,
    VerificationState,
)


def report_fixture():
    confirmed = ContactEvidence(
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
    probable = ContactEvidence(
        email="john.doe@acme.com",
        state=VerificationState.PROBABLE,
        confidence=0.78,
        source="empire_pattern_brain",
        source_url="https://acme.com/team",
        person_name="John Doe",
        person_title="COO",
        person_bound=True,
        first_party=False,
        syntax_ok=True,
        mx_ok=True,
    )
    return DomainIntelligenceReport(
        requested_url="https://acme.com",
        domain="acme.com",
        business_names=("Acme Roofing",),
        contacts=(confirmed, probable),
        pattern=DomainPattern(
            domain="acme.com",
            pattern="first.last",
            observations=1,
            agreement=1.0,
            confidence=0.66,
        ),
        pages_checked=2,
        evidence_score=0.9,
    )


def test_evidence_plan_maps_to_existing_intelligence_fabric_shape():
    entity_id = str(uuid4())
    observed = datetime(
        2026, 9, 20, 14, 0, tzinfo=timezone.utc
    )
    plan = build_evidence_plan(
        report_fixture(),
        entity_id=entity_id,
        observed_at=observed,
    )

    assert plan.entity_id == entity_id
    assert plan.source_key == "empire_hunter:first_party:acme.com"
    assert len(plan.people) == 2
    assert len(plan.employments) == 2
    assert len(plan.contacts) == 2
    assert len(plan.facts) == 1
    assert plan.write_authorized is False

    confirmed = next(
        row for row in plan.contacts
        if row.normalized_value == "jane.smith@acme.com"
    )
    probable = next(
        row for row in plan.contacts
        if row.normalized_value == "john.doe@acme.com"
    )
    assert confirmed.verification_state == "confirmed"
    assert confirmed.verified_at is not None
    assert probable.verification_state == "probable"
    assert probable.verified_at is None


def test_evidence_hash_is_stable_and_content_addressed():
    one = evidence_hash(
        "company",
        "entity",
        "email_domain_pattern",
        {"pattern": "first.last"},
        "https://acme.com",
    )
    two = evidence_hash(
        "company",
        "entity",
        "email_domain_pattern",
        {"pattern": "first.last"},
        "https://acme.com",
    )
    changed = evidence_hash(
        "company",
        "entity",
        "email_domain_pattern",
        {"pattern": "flast"},
        "https://acme.com",
    )

    assert one == two
    assert one != changed


def test_invalid_entity_id_fails_closed():
    try:
        build_evidence_plan(
            report_fixture(),
            entity_id="not-a-uuid",
        )
    except ValueError as exc:
        assert "entity_id" in str(exc)
    else:
        raise AssertionError("invalid entity id did not fail closed")
