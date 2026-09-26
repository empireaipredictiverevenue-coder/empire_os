from empire_os.buyer_acquisition_scout import (
    CONTINUOUS_COMMERCIAL_LANE_BY_ICP,
)
from empire_os.icp_buyer_trigger_intelligence import ICP_PROFILES


def test_home_service_icp_can_buy_permit_intelligence():
    profile = next(
        row
        for row in ICP_PROFILES
        if row["profile_key"] == "high_ticket_home_service"
    )

    assert "permit_intelligence" in profile["product_codes"]
    assert "plumbing" in profile["industry_signals"]
    assert "general contractor" in profile["industry_signals"]


def test_home_service_is_continuous_permit_demand_lane():
    assert CONTINUOUS_COMMERCIAL_LANE_BY_ICP[
        "high_ticket_home_service"
    ] == "permit_home_services"
