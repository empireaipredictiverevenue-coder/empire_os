from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_doctor_flags_false_registry_company_from_existing_receipt():
    import importlib.util
    filename = ROOT / "scripts/verify_buyer_acquisition_automation.py"
    spec = importlib.util.spec_from_file_location("buyer_plumbing_doctor", filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sample = {
        "updates": [{
            "candidate_id": "bad-registry-join",
            "response": [{
                "id": "bad-registry-join",
                "review_state": "review_ready",
                "reconciliation_state": "REVIEW_READY",
                "business_name": "Harvey",
                "query_evidence": [{
                    "query": '"HARVEY HVAC SERVICES LLC" TX',
                    "source_refs": ["official:texas_tdlr_ac:118954"],
                }],
                "site_evidence": {
                    "business_name_source": "first_party_site_identity",
                    "site_business_names": ["Harvey AI"],
                },
            }],
        }],
    }
    assert module._review_receipt_identity_mismatches(sample) == [
        "bad-registry-join"
    ]
    assert module._review_receipt_identity_mismatches({"updates": []}) == []


def test_buyer_acquisition_verifier_requires_safe_internal_team():
    text = (
        ROOT / "scripts/verify_buyer_acquisition_automation.py"
    ).read_text()

    for unit in (
        "empire-qualification.timer",
        "empire-buyer-review-materializer.timer",
        "empire-buyer-deferred-enrichment.timer",
        "empire-buyer-capacity-readiness.timer",
        "empire-commercial-evidence-auto-verifier.timer",
        "empire-commercial-product-catalog.timer",
        "empire-commercial-exchange.timer",
        "empire-buyer-acquisition-team.timer",
        "empire-buyer-acquisition-scout.timer",
    ):
        assert unit in text

    assert '"safe_internal_automation_ready"' in text
    assert '"production_ready"' in text


def test_buyer_acquisition_verifier_treats_live_send_units_as_external_gate():
    text = (
        ROOT / "scripts/verify_buyer_acquisition_automation.py"
    ).read_text()

    assert "empire-outbound-governor.timer" in text
    assert "empire-outbound-followup.timer" in text
    assert "empire-voice-outbound.timer" in text
    assert "live_external_automation_detected" in text
    assert "live_external_automation_is_separate_gate" in text
    assert "not live_external_automation_detected" not in text


def test_buyer_acquisition_verifier_requires_catalog_and_scout_artifacts():
    text = (
        ROOT / "scripts/verify_buyer_acquisition_automation.py"
    ).read_text()

    assert "runtime/commercial_catalog/latest.json" in text
    assert "runtime/commercial_exchange/latest.json" in text
    assert "runtime/buyer_acquisition/latest.json" in text
    assert "runtime/buyer_acquisition/scout_latest.json" in text


def test_buyer_acquisition_verifier_requires_scout_artifact():
    text = (
        ROOT / "scripts/verify_buyer_acquisition_automation.py"
    ).read_text()

    assert "runtime/buyer_acquisition/scout_latest.json" in text
    assert "buyer_scout_safe" in text
    assert "database_write_performed" in text


def test_buyer_acquisition_verifier_requires_reconciliation_artifact():
    text = (
        ROOT / "scripts/verify_buyer_acquisition_automation.py"
    ).read_text()

    assert "runtime/buyer_acquisition/reconciliation_latest.json" in text
    assert "buyer_scout_reconciliation_safe" in text
    assert "automatic_ingest_authorized" in text


def test_buyer_acquisition_verifier_requires_holding_persistence():
    text = (
        ROOT / "scripts/verify_buyer_acquisition_automation.py"
    ).read_text()

    assert "runtime/buyer_acquisition/persistence_latest.json" in text
    assert "buyer_scout_persistence_safe" in text
    assert "holding_area_only" in text
    assert "canonical_promotion_performed" in text


def test_buyer_acquisition_verifier_requires_pricing_drift_artifact():
    text = (
        ROOT / "scripts/verify_buyer_acquisition_automation.py"
    ).read_text()

    assert "pricing_verification_latest.json" in text
    assert "pricing_policy_safe" in text
    assert "pricing_matches_approved_policy" in text


def test_buyer_acquisition_verifier_requires_review_readiness():
    text = (
        ROOT / "scripts/verify_buyer_acquisition_automation.py"
    ).read_text()

    assert "review_readiness_latest.json" in text
    assert "buyer_scout_review_readiness_safe" in text
    assert "review_ready_candidate_count" in text


def test_buyer_acquisition_verifier_requires_safe_promotion_plan():
    text = (
        ROOT / "scripts/verify_buyer_acquisition_automation.py"
    ).read_text()

    assert "promotion_plan_latest.json" in text
    assert "buyer_scout_promotion_plan_safe" in text
    assert "buy_signal_score_policy" in text
    assert "UNKNOWN_NULL" in text
