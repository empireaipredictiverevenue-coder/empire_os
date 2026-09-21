import pytest

from empire_os.spatial_physical_intelligence import (
    PhysicalObservation,
    SpatialPhysicalOpportunity,
    VolumetricObservation,
)


def test_volumetric_observation_requires_real_evidence_and_no_execution():
    row = VolumetricObservation(
        subject_ref="property:123",
        source="lidar",
        observed_at="2026-09-21T16:00:00Z",
        representation="point_cloud",
        evidence_refs=("evidence:lidar:abc",),
        confidence=0.91,
    )
    assert row.execution_authority == "none"
    assert row.as_dict()["representation"] == "point_cloud"

    with pytest.raises(ValueError):
        VolumetricObservation(
            subject_ref="property:123",
            source="lidar",
            observed_at="2026-09-21T16:00:00Z",
            representation="point_cloud",
            evidence_refs=(),
        )


def test_physical_observation_preserves_measured_values_only():
    row = PhysicalObservation(
        subject_ref="property:123",
        source="thermal_imagery",
        observed_at="2026-09-21T16:00:00Z",
        phenomenon="thermal_loss",
        evidence_refs=("evidence:thermal:abc",),
        measurements={"surface_delta_c": 8.4},
        units={"surface_delta_c": "celsius"},
    )
    assert row.as_dict()["measurements"]["surface_delta_c"] == 8.4

    with pytest.raises(ValueError):
        PhysicalObservation(
            subject_ref="property:123",
            source="thermal_imagery",
            observed_at="2026-09-21T16:00:00Z",
            phenomenon="thermal_loss",
            evidence_refs=("evidence:thermal:abc",),
            units={"invented_measurement": "celsius"},
        )


def test_spatial_physical_opportunity_stays_modeled_and_read_only():
    row = SpatialPhysicalOpportunity(
        subject_ref="property:123",
        opportunity_type="roof_repair",
        physical_basis="observed roof-surface change after verified hail event",
        evidence_refs=("evidence:storm:1", "evidence:surface:2"),
        confidence=0.78,
    )
    assert row.modeled_only is True
    assert row.execution_authority == "none"

    with pytest.raises(ValueError):
        SpatialPhysicalOpportunity(
            subject_ref="property:123",
            opportunity_type="roof_repair",
            physical_basis="modeled",
            evidence_refs=("evidence:1",),
            modeled_only=False,
        )
