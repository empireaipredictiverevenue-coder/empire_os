from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_continuous_enterprise_scout_deployer_is_bounded():
    text = (
        ROOT / "scripts/deploy_continuous_enterprise_scout.sh"
    ).read_text()

    assert "test_icp_buyer_trigger_intelligence.py" in text
    assert "test_buyer_acquisition_scout.py" in text
    assert "empire-buyer-acquisition-scout.timer" in text
    assert "enable --now" in text
    assert "RUN FIRST ENTERPRISE DISCOVERY CYCLE" in text
    assert "predictive_revenue_enterprise_candidate_count" in text
    assert "30-minute Buyer Scout loop" in text
    assert "send_outbound" not in text
    assert "payment" not in text.lower()
