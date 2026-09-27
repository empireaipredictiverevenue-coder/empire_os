from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_continuous_buyer_lanes_deployer_is_bounded_and_governed():
    text = (
        ROOT / "scripts/deploy_continuous_buyer_lanes.sh"
    ).read_text()

    assert "test_icp_buyer_trigger_intelligence.py" in text
    assert "test_buyer_acquisition_scout.py" in text
    assert "empire-buyer-acquisition-scout.timer" in text
    assert "enable --now" in text
    assert "RUN FIRST CONTINUOUS DISCOVERY CYCLE" in text
    assert "continuous_lane_candidate_counts" in text
    assert "Predictive Revenue / Legal Mass Tort / Legal / Insurance" in text
    assert "Individual plaintiff targeting: OFF" in text
    assert "outbound_sent" in text
    assert "send_outbound" not in text
