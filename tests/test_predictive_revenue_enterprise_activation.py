from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_enterprise_activation_uses_canonical_existing_workers():
    text = (
        ROOT
        / "scripts/activate_predictive_revenue_enterprise_targets.py"
    ).read_text()

    assert "ingest_candidate(candidate)" in text
    assert "qualify_prospect(prospect)" in text
    assert "probe_buyer(" in text
    assert '"live_outbound_send": False' in text
    assert '"outreach_authorized": False' in text
    assert '"payment_action": False' in text
    assert '"actual_revenue": False' in text
    assert "allow_company_routed=False" in text
