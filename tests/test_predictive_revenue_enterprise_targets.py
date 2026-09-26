from empire_os.predictive_revenue_enterprise_targets import (
    TARGETS,
    build_enterprise_target_review,
)


def test_enterprise_target_review_is_internal_only():
    payload = build_enterprise_target_review()
    assert payload["status"] == "INTERNAL_REVIEW_ONLY"
    assert payload["target_count"] == 9
    assert payload["outreach_authorized"] is False
    assert payload["payment_action"] is False
    assert payload["actual_revenue"] is False
    assert payload["execution_authority"] == "none"
    assert payload["truth_rules"]["public_fit_is_buyer_intent"] is False
    assert payload["truth_rules"]["synthetic_targets_allowed"] is False


def test_every_target_has_evidence_and_no_execution_authority():
    assert len(TARGETS) == 9
    for target in TARGETS:
        row = target.as_dict()
        assert row["evidence_urls"]
        assert row["target_product_codes"]
        assert row["campaign_angle"]
        assert row["binding_intent_verified"] is False
        assert row["contact_verified"] is False
        assert row["outreach_authorized"] is False
        assert row["actual_revenue"] is False
        assert row["execution_authority"] == "none"


def test_target_keys_are_unique():
    keys = [target.account_key for target in TARGETS]
    assert len(keys) == len(set(keys))


def test_home_services_and_sponsor_waves_are_both_present():
    waves = {target.wave for target in TARGETS}
    assert waves == {"direct_enterprise", "sponsor_enterprise"}
