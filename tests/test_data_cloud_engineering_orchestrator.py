from empire_os.data_cloud_engineering_orchestrator import (
    default_data_cloud_lanes,
    engineering_authority_contract,
    lanes_have_non_overlapping_ownership,
)


def test_data_cloud_parallel_lanes_have_isolated_ownership():
    lanes = default_data_cloud_lanes()
    assert len(lanes) == 5
    assert lanes_have_non_overlapping_ownership(lanes) is True


def test_every_lane_has_tests_and_independent_verifier():
    for lane in default_data_cloud_lanes():
        assert lane.required_tests
        assert lane.independent_verifier == "swarm_v6"
        assert lane.authority == "internal_write"


def test_engineering_orchestrator_has_no_production_authority():
    authority = engineering_authority_contract()
    assert authority["production_deploy"] is False
    assert authority["canonical_data_write"] is False
    assert authority["schema_mutation"] is False
    assert authority["external_send"] is False
    assert authority["fund_movement"] is False
    assert authority["revenue_recognition"] is False
    assert authority["authority_expansion"] is False
    assert authority["independent_verification_required"] is True
