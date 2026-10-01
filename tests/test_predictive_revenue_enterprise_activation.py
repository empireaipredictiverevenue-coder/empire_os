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


def test_enterprise_activation_reads_canonical_empiredb():
    text = (ROOT / "scripts/activate_predictive_revenue_enterprise_targets.py").read_text()
    assert "fetch_prospect(prospect_id)" in text
    assert "request_json" not in text
    assert "urllib.parse" not in text


def test_enterprise_activation_includes_verified_rolling_pool():
    text = (ROOT / "scripts/activate_predictive_revenue_enterprise_targets.py").read_text()
    assert "_rolling_candidates()" in text
    assert "rolling enterprise candidate from buyer scout promotion pool" in text
    assert '"outreach_authorized": False' in text


def test_rolling_activation_revalidates_first_party_location():
    text = (ROOT / "scripts/activate_predictive_revenue_enterprise_targets.py").read_text()
    assert "location_from_addresses(" in text
    assert "location_evidence_addresses" in text


def test_rolling_enterprise_wave_is_semantic_and_sort_safe():
    text = (ROOT / "scripts/activate_predictive_revenue_enterprise_targets.py").read_text()
    assert '"wave": "rolling_enterprise"' in text
    assert 'str(row["wave"])' in text
