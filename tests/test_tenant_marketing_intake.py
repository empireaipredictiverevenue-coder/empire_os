from datetime import datetime, timezone

from empire_os.tenant_marketing_intake import (
    build_tenant_marketing_intake,
    tenant_marketing_intake_matches,
)


NOW = datetime(2026, 10, 5, 9, 30, tzinfo=timezone.utc)


def test_build_is_deterministic_and_planning_only():
    kwargs = {
        "tenant_id": "tenant-1",
        "opportunity_key": "storm:test",
        "evidence_refs": ["storm:event:1", "storm:subject:1"],
        "authorized_at": "2026-10-05T09:30:00+00:00",
    }

    first = build_tenant_marketing_intake(**kwargs)
    second = build_tenant_marketing_intake(**kwargs)

    assert first["intake_id"] == second["intake_id"]
    assert first["planning_authorized"] is True

    for field in (
        "execution_authority",
        "outreach_authority",
        "traffic_authority",
        "call_authority",
        "commercial_authority",
        "payment_authority",
        "revenue_recognition_authority",
    ):
        assert first[field] == "none"


def test_matching_intake_requires_exact_tenant_and_opportunity():
    intake = build_tenant_marketing_intake(
        tenant_id="tenant-1",
        opportunity_key="storm:test",
        evidence_refs=["storm:event:1"],
        authorized_at="2026-10-05T09:30:00+00:00",
    )

    assert tenant_marketing_intake_matches(
        intake,
        tenant_id="tenant-1",
        opportunity_key="storm:test",
        now=NOW,
    )

    assert not tenant_marketing_intake_matches(
        intake,
        tenant_id="tenant-2",
        opportunity_key="storm:test",
        now=NOW,
    )

    assert not tenant_marketing_intake_matches(
        intake,
        tenant_id="tenant-1",
        opportunity_key="storm:other",
        now=NOW,
    )


def test_hostile_authority_expansion_fails_closed():
    intake = build_tenant_marketing_intake(
        tenant_id="tenant-1",
        opportunity_key="storm:test",
        evidence_refs=["storm:event:1"],
        authorized_at="2026-10-05T09:30:00+00:00",
    )

    hostile = dict(intake)
    hostile["traffic_authority"] = "activate"

    assert not tenant_marketing_intake_matches(
        hostile,
        tenant_id="tenant-1",
        opportunity_key="storm:test",
        now=NOW,
    )

def test_missing_intake_does_not_match():
    assert not tenant_marketing_intake_matches(
        None,
        tenant_id="tenant-1",
        opportunity_key="storm:test",
        now=NOW,
    )


def test_empty_evidence_fails_closed():
    intake = {
        "schema_version": "empire.tenant_marketing_intake.v1",
        "tenant_id": "tenant-1",
        "opportunity_key": "storm:test",
        "purpose": "marketing_agency_planning",
        "planning_authorized": True,
        "evidence_refs": [],
        "execution_authority": "none",
        "outreach_authority": "none",
        "traffic_authority": "none",
        "call_authority": "none",
        "commercial_authority": "none",
        "payment_authority": "none",
        "revenue_recognition_authority": "none",
    }

    assert not tenant_marketing_intake_matches(
        intake,
        tenant_id="tenant-1",
        opportunity_key="storm:test",
        now=NOW,
    )


def test_stale_authorization_fails_closed():
    from datetime import datetime, timezone

    intake = build_tenant_marketing_intake(
        tenant_id="tenant-1",
        opportunity_key="observed:test",
        evidence_refs=["canonical:auth:1"],
        authorized_at="2026-09-29T11:59:59+00:00",
    )
    assert tenant_marketing_intake_matches(
        intake,
        tenant_id="tenant-1",
        opportunity_key="observed:test",
        now=datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc),
    ) is False


def test_future_authorization_fails_closed():
    from datetime import datetime, timezone

    intake = build_tenant_marketing_intake(
        tenant_id="tenant-1",
        opportunity_key="observed:test",
        evidence_refs=["canonical:auth:1"],
        authorized_at="2026-09-30T12:01:01+00:00",
    )
    assert tenant_marketing_intake_matches(
        intake,
        tenant_id="tenant-1",
        opportunity_key="observed:test",
        now=datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc),
    ) is False


def test_malformed_authorization_timestamp_fails_closed():
    from datetime import datetime, timezone

    intake = build_tenant_marketing_intake(
        tenant_id="tenant-1",
        opportunity_key="observed:test",
        evidence_refs=["canonical:auth:1"],
        authorized_at="not-a-time",
    )
    assert tenant_marketing_intake_matches(
        intake,
        tenant_id="tenant-1",
        opportunity_key="observed:test",
        now=datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc),
    ) is False


def test_timezone_less_authorization_fails_closed():
    from datetime import datetime, timezone

    intake = build_tenant_marketing_intake(
        tenant_id="tenant-1",
        opportunity_key="observed:test",
        evidence_refs=["canonical:auth:1"],
        authorized_at="2026-09-30T12:00:00",
    )
    assert tenant_marketing_intake_matches(
        intake,
        tenant_id="tenant-1",
        opportunity_key="observed:test",
        now=datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc),
    ) is False
