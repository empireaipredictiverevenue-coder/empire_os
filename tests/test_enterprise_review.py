from empire_os.enterprise_controls import ControlEvidence, SloObservation
from empire_os.enterprise_review import review_enterprise_readiness


def control(status):
    return ControlEvidence(
        control_key=f"control-{status}",
        family="auditability",
        tenant_key="tenant-1",
        status=status,
        evidence_refs=(f"evidence:{status}",),
        observed_at="2026-09-19T23:30:00+00:00",
        source="control_probe",
    )


def slo(observed):
    return SloObservation(
        service_key="public-gateway",
        metric="availability",
        target=0.99,
        observed=observed,
        window="30d",
        observed_at="2026-09-19T23:30:00+00:00",
        source="slo_probe",
    )


def test_clean_evidence_is_ready_for_enterprise_review_only():
    result = review_enterprise_readiness(
        controls=[control("pass")],
        slos=[slo(0.995)],
    )
    assert result.ready_for_enterprise_review is True
    assert result.blockers == ()
    assert result.execution_authority == "none"


def test_unknown_controls_block_readiness():
    result = review_enterprise_readiness(
        controls=[control("unknown")],
        slos=[slo(0.995)],
    )
    assert result.ready_for_enterprise_review is False
    assert "control_unknowns_present" in result.blockers


def test_failed_slo_blocks_readiness():
    result = review_enterprise_readiness(
        controls=[control("pass")],
        slos=[slo(0.95)],
    )
    assert result.ready_for_enterprise_review is False
    assert "slo_failures_present" in result.blockers


def test_unknown_slo_blocks_readiness():
    result = review_enterprise_readiness(
        controls=[control("pass")],
        slos=[slo(None)],
    )
    assert result.ready_for_enterprise_review is False
    assert "slo_unknowns_present" in result.blockers


def test_missing_evidence_sets_explicit_blockers():
    result = review_enterprise_readiness(
        controls=[],
        slos=[],
    )
    assert result.ready_for_enterprise_review is False
    assert result.blockers == (
        "no_control_evidence",
        "no_slo_observations",
    )
