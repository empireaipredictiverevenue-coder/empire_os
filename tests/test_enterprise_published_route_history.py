"""Published partnerships inbox history must stay review-only."""

import pytest

from empire_os.enterprise_published_route_history import review_published_route
from scripts.inspect_champions_published_route_readonly import select_route
from tests.test_enterprise_domain_history_readonly import FakeConnection
from tests.test_predictive_revenue_enterprise_commercial_review import fixtures
from empire_os.predictive_revenue_enterprise_commercial_review import build_review


def args():
    return dict(
        email="Partnerships@championsgh.com",
        source_url="https://championsgroupholdings.com/contact/",
        company_domain="championsgroupholdings.com",
    )


def test_published_route_exact_history_read_only_and_unapproved():
    conn = FakeConnection([(False, 0, 0)])
    out = review_published_route("fixture", connect_factory=lambda _: conn, **args())
    assert out["published_email"] == "partnerships@championsgh.com"
    assert out["prior_exact_outbound_intent_count"] == 0
    assert out["prior_exact_send_or_reply_event_count"] == 0
    assert out["suppression_match_observed"] is False
    assert out["known_domain_alias_on_official_site"] is True
    assert out["verified_software_procurement_route"] is False
    assert out["person_bound"] is False
    assert out["recipient_send_time_suppression_cleared"] is False
    assert out["outreach_authorized"] is False
    assert out["outbound_sent"] is False
    assert out["database_writes"] is False
    assert conn.cur.executed[0][0] == "SET TRANSACTION READ ONLY"
    assert conn.cur.executed[-1][0] == "ROLLBACK"
    assert conn.cur.executed[2][1] == ("partnerships@championsgh.com",)


def test_positive_history_and_suppression_never_turn_into_clearance():
    out = review_published_route(
        "fixture", connect_factory=lambda _: FakeConnection([(True, 3, 1)]), **args()
    )
    assert out["suppression_match_observed"] is True
    assert out["prior_exact_outbound_intent_count"] == 3
    assert out["prior_exact_send_or_reply_event_count"] == 1
    assert out["outreach_authorized"] is False


def test_guessed_person_email_and_wrong_source_rejected():
    with pytest.raises(ValueError, match="UNVERIFIED_EMAIL_OR_INFERRED_PERSON_MAILBOX"):
        review_published_route("fixture", **dict(args(), email="laura@championsgh.com"))
    with pytest.raises(ValueError, match="NOT_OFFICIAL_PUBLISHED_CONTACT_PAGE"):
        review_published_route("fixture", **dict(args(), source_url="https://evil.example/contact/"))
    with pytest.raises(ValueError, match="INVALID_CURATED_PUBLISHED_ROUTE"):
        review_published_route("fixture", **dict(args(), company_domain="championsgh.com"))


def test_malformed_canonical_reader_fails_closed():
    with pytest.raises(ValueError, match="INVALID_CANONICAL_ROUTE_HISTORY_READBACK"):
        review_published_route("fixture", connect_factory=lambda _: FakeConnection([(0, 0, 0)]), **args())
    with pytest.raises(ValueError, match="CANONICAL_EMPIREDB_DSN_REQUIRED"):
        review_published_route("", **args())


def test_cli_selects_only_published_unapproved_curated_route():
    pool, locations, promotion = fixtures()
    for row in (pool["rolling_candidates"][0], locations["candidates"][0]):
        row.update({"domain": "championsgroupholdings.com", "candidate_id": "champs-1",
                    "account_name": "Champions Group Holdings", "website": "https://championsgroupholdings.com/"})
    promotion["proposals"][0].update({"domain": "championsgroupholdings.com", "candidate_id": "champs-1"})
    review = build_review(pool, locations, promotion)
    route = select_route(review)
    assert route["published_email"] == "Partnerships@championsgh.com"
    route["software_vendor_fit_verified"] = True
    with pytest.raises(ValueError, match="CURATED_PUBLISHED_ROUTE_UNAVAILABLE"):
        select_route(review)


def test_market_role_nested_review_data_is_immutable_across_callers():
    from empire_os.enterprise_public_market_role_review import market_role_review

    first = market_role_review("championsgroupholdings.com")
    first["public_contact_routes_for_review_only"][0]["software_vendor_fit_verified"] = True
    first["observed_buyer_roles_for_review_only"][0]["person_email_binding_verified"] = True
    first["testable_discovery_questions"].clear()
    second = market_role_review("championsgroupholdings.com")
    assert second["public_contact_routes_for_review_only"][0]["software_vendor_fit_verified"] is False
    assert second["observed_buyer_roles_for_review_only"][0]["person_email_binding_verified"] is False
    assert len(second["testable_discovery_questions"]) == 3
