import pytest

from empire_os.enterprise_controls import ControlEvidence, SloObservation


def test_control_evidence_requires_provenance():
    control = ControlEvidence(
        control_key="tenant_row_isolation",
        family="data_isolation",
        tenant_key="tenant-1",
        status="pass",
        evidence_refs=("rls-policy:test",),
        observed_at="2026-09-19T22:00:00+00:00",
        source="canonical_control_probe",
    )
    payload = control.as_dict()
    assert payload["status"] == "pass"
    assert payload["tenant_key"] == "tenant-1"


def test_unknown_control_status_is_explicitly_allowed():
    control = ControlEvidence(
        control_key="backup_restore_test",
        family="backup_dr",
        tenant_key=None,
        status="unknown",
        evidence_refs=("runbook:backup-dr",),
        observed_at="2026-09-19T22:00:00+00:00",
        source="control_registry",
    )
    assert control.as_dict()["status"] == "unknown"


def test_control_without_evidence_fails_closed():
    with pytest.raises(ValueError, match="requires evidence refs"):
        ControlEvidence(
            control_key="tenant_row_isolation",
            family="data_isolation",
            tenant_key="tenant-1",
            status="pass",
            evidence_refs=(),
            observed_at="2026-09-19T22:00:00+00:00",
            source="probe",
        ).validate()


def test_slo_unknown_observation_stays_unknown():
    slo = SloObservation(
        service_key="public-gateway",
        metric="availability",
        target=0.999,
        observed=None,
        window="30d",
        observed_at="2026-09-19T22:00:00+00:00",
        source="slo_probe",
    )
    assert slo.meets_target is None


def test_slo_comparison_is_deterministic():
    slo = SloObservation(
        service_key="public-gateway",
        metric="availability",
        target=0.99,
        observed=0.995,
        window="30d",
        observed_at="2026-09-19T22:00:00+00:00",
        source="slo_probe",
    )
    assert slo.meets_target is True
