"""Founder-provided domain history must never become recipient clearance."""
from copy import deepcopy
import json

import pytest

from empire_os.enterprise_domain_history_attestation import apply_operator_domain_readback
from scripts.build_predictive_revenue_enterprise_commercial_review import run
from tests.test_predictive_revenue_enterprise_commercial_review import fixtures


def evidence():
    pool, locations, promotion = fixtures()
    from empire_os.predictive_revenue_enterprise_commercial_review import build_review
    review = build_review(pool, locations, promotion)
    domain = "example.com"
    readback = {
        "schema_version": "empire.enterprise-domain-history-readonly.v1",
        "source": "CANONICAL_EMPIREDB", "mode": "OBSERVE", "database_transaction": "READ_ONLY",
        "database_writes": False, "outbound_sent": False,
        "founder_send_authorized": False, "individual_recipient_suppression_cleared": False,
        "domain_count": 1,
        "domain_results": {domain: {
            "prior_canonical_intent_observed": False,
            "canonical_send_or_reply_event_observed": False,
            "any_suppression_on_domain_observed": False,
            "domain_contact_history_state": "NO_DOMAIN_HISTORY_OBSERVED_NOT_SEND_CLEARANCE",
            "recipient_identity_verified": False,
            "individual_recipient_suppression_cleared": False,
            "outreach_authorized": False,
        }},
    }
    return review, readback


def test_negative_operator_readback_is_observation_not_clearance():
    review, readback = evidence()
    amended = apply_operator_domain_readback(review, readback, expected_domains=["example.com"])
    packet = amended["packets"][0]
    assert amended["founder_operator_domain_history_observed"] is True
    assert amended["domain_history_observation_count"] == 1
    assert amended["outreach_authorized"] is False
    assert amended["domain_history_readback_is_send_clearance"] is False
    assert packet["domain_history_observation"]["history_state"] == "NO_DOMAIN_HISTORY_OBSERVED_NOT_SEND_CLEARANCE"
    assert packet["prior_contact_status"] == "UNKNOWN_RECHECK_REQUIRED"
    assert packet["suppression_status"] == "UNKNOWN_SEND_TIME_CHECK_REQUIRED"
    assert packet["outreach_authorized"] is False
    assert "PRIOR_CONTACT_RECHECK_REQUIRED" in packet["blockers"]
    assert "domain_history_observation" not in review["packets"][0]


def test_positive_suppression_remains_visible_and_never_authorizes():
    review, readback = evidence()
    readback["domain_results"]["example.com"]["any_suppression_on_domain_observed"] = True
    amended = apply_operator_domain_readback(review, readback, expected_domains=["example.com"])
    assert amended["packets"][0]["domain_history_observation"]["suppression_on_domain_observed"] is True
    assert amended["outreach_authorized"] is False


def test_cohort_drift_and_tampering_fail_closed():
    review, readback = evidence()
    with pytest.raises(ValueError, match="STALE_OR_INCOMPLETE"):
        apply_operator_domain_readback(review, readback, expected_domains=["another.example"])
    altered = deepcopy(readback)
    altered["domain_results"]["example.com"]["individual_recipient_suppression_cleared"] = True
    with pytest.raises(ValueError, match="INVALID_DOMAIN_ATTESTATION"):
        apply_operator_domain_readback(review, altered, expected_domains=["example.com"])
    altered = deepcopy(readback)
    altered["domain_results"]["example.com"]["domain_contact_history_state"] = "PRIOR_HISTORY_OBSERVED"
    with pytest.raises(ValueError, match="INCONSISTENT"):
        apply_operator_domain_readback(review, altered, expected_domains=["example.com"])


def test_optional_attestation_path_in_snapshot_builder(tmp_path):
    pool, locations, promotion = fixtures()
    _review, readback = evidence()
    files = {
        "runtime/predictive_revenue/enterprise_pool_latest.json": pool,
        "runtime/predictive_revenue/enterprise_location_enrichment_latest.json": locations,
        "runtime/buyer_acquisition/promotion_plan_latest.json": promotion,
        "runtime/predictive_revenue/enterprise_domain_history_operator_readback_latest.json": readback,
    }
    for name, value in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
    result = run(tmp_path)
    assert result["domain_history_observation_count"] == 1
    assert result["packets"][0]["suppression_status"] == "UNKNOWN_SEND_TIME_CHECK_REQUIRED"
    assert result["outreach_authorized"] is False


def test_website_history_does_not_clear_different_published_mailbox_domain():
    review, readback = evidence()
    review["packets"][0]["market_role_review"] = {
        "public_contact_routes_for_review_only": [
            {"published_email": "Partnerships@championsgh.com"}
        ]
    }
    amended = apply_operator_domain_readback(
        review, readback, expected_domains=["example.com"]
    )
    packet = amended["packets"][0]
    assert packet["uninspected_published_contact_domains"] == ["championsgh.com"]
    assert "PUBLISHED_CONTACT_DOMAIN_HISTORY_UNCHECKED" in packet["blockers"]
    assert packet["outreach_authorized"] is False
    assert packet["suppression_status"] == "UNKNOWN_SEND_TIME_CHECK_REQUIRED"
