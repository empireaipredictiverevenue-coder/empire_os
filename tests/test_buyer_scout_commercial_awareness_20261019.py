"""Business-aware dedup review, using synthetic records, never contacting buyers."""
from datetime import datetime, timezone, timedelta
import json
import pytest

from empire_os.buyer_scout_commercial_awareness import review_buyer_scout_awareness


NOW = datetime(2026, 10, 19, 19, 50, tzinfo=timezone.utc)
NOW_STAMP = NOW.isoformat()

def sources(candidates=None, targets=None, relationships=None, **kwargs):
    scout = {"schema_version": "empire.buyer_acquisition_scout.v1",
             "generated_at": NOW_STAMP, "mode": "OBSERVE",
             "execution_authority": "none", "outbound_sent": False,
             "candidates": candidates or []}
    actions = {"schema_version": "empire.buyer_qualification_actions.v1",
               "generated_at": NOW_STAMP, "mode": "OBSERVE",
               "execution_authority": "none", "outbound_sent": False,
               "outbound_enabled": False, "targets": targets or []}
    registry = {"schema_version": "empire.commercial_relationship_registry.v1",
                "generated_at": NOW_STAMP, "mode": "OBSERVE",
                "execution_authority": "NONE", "outbound_sent": False,
                "outbound_authorized": False, "gmail_snapshot_fresh": False,
                "relationships": relationships or []}
    for key,value in kwargs.items():
        {"scout":scout,"actions":actions,"registry":registry}[key].update(value)
    return scout,actions,registry


def review(*args, prior=None):
    return review_buyer_scout_awareness(*args, as_of=NOW, prior_scout=prior)


def test_duplicates_same_domain_only_single_research_task():
    s,a,r = sources([
        {"domain":"https://www.buyer.co.uk/research","buyer_relationship":"unknown"},
        {"domain":"buyer.co.uk","buyer_relationship":"unknown"}
    ],[{"domain":"buyer.co.uk"}])
    d=review(s,a,r)
    assert d["source_candidate_rows"] == 2
    assert d["unique_exact_business_domains"] == 1
    assert d["duplicate_scout_rows"] == 1
    assert d["review_queue"][0]["next_evidence_task"] == "VERIFY_FIRST_PARTY_DIRECT_BUYBOX_AND_DEMAND"
    assert d["buyer_activation_authorized"] is False
    assert d["outbound_authorized"] is False


def test_company_names_not_used_as_entity_merge():
    s,a,r = sources([{"domain":"brand-a.com", "business_name":"Same Name"},
                     {"domain":"brand-b.com", "business_name":"Same Name"}])
    d=review(s,a,r)
    assert d["unique_exact_business_domains"] == 2
    assert d["same_name_different_domain_not_automatically_merged"] is True


def test_prior_relationship_and_stale_gmail_forces_thread_review():
    s,a,r=sources([{"domain":"brand.com"}],[{"domain":"brand.com"}],
                   [{"identity_domains":["brand.com","brand.co.uk"],
                     "last_outbound_at":"2026-10-01T10:00:00+00:00",
                     "gmail_thread_ids":["private-thread"],"do_not_pursue":False}])
    d=review(s,a,r)
    row=d["review_queue"][0]
    assert row["prior_contact_or_thread_evidence"] is True
    assert row["next_evidence_task"] == "REFRESH_EXISTING_THREAD_BEFORE_ANY_CONTACT"
    assert "private-thread" not in json.dumps(d)
    assert d["previously_contacted_or_engaged_domains"] == 1


def test_suppression_and_bounce_hard_hold():
    s,a,r=sources([{"domain":"brand.com"}],[],
                   [{"identity_domains":["brand.com"],"bounced_addresses":["private@brand.com"],
                     "do_not_pursue":False}])
    d=review(s,a,r)
    assert d["review_queue"][0]["next_evidence_task"] == "SUPPRESSION_REVIEW_ONLY"
    assert d["review_queue"][0]["research_priority_not_conversion_probability"] == 0
    assert d["suppressed_or_bounced_domains"] == 1
    assert "private@brand.com" not in json.dumps(d)


def test_identity_alias_collision_is_held_not_merged():
    s,a,r=sources([{"domain":"brand.com"}],[],
                   [{"identity_domains":["brand.com"],"do_not_pursue":False},
                    {"identity_domains":["brand.com"],"do_not_pursue":False}])
    d=review(s,a,r)
    assert d["review_queue"][0]["next_evidence_task"] == "RESOLVE_IDENTITY_ALIAS_CONFLICT"


def test_intermediary_without_own_spend_not_classed_direct():
    s,a,r=sources([{"domain":"network.com","buyer_relationship":"intermediary_or_marketplace",
                    "explicit_direct_buyer_evidence":False}], [{"domain":"network.com"}])
    d=review(s,a,r)
    assert d["review_queue"][0]["buyer_role_for_review"] == "INTERMEDIARY_OR_PUBLISHER"
    assert d["review_queue"][0]["next_evidence_task"] == "VERIFY_INTERMEDIARY_OWN_SPEND_VS_PUBLISHER_RECRUITMENT"
    assert d["review_queue"][0]["buyer_budget_authenticated"] is False


def test_direct_buyer_claim_still_needs_identity_then_budget_and_terms():
    row={"domain":"brand.com","buyer_relationship":"direct_buyer",
         "explicit_direct_buyer_evidence":True,
         "buyer_claim_provenance":{"explicit_direct_purchase_observed":True},
         "canonical_identity_verified":False}
    s,a,r=sources([row],[{"domain":"brand.com"}])
    assert review(s,a,r)["review_queue"][0]["next_evidence_task"] == "RECONCILE_CANONICAL_BUSINESS_IDENTITY_WITH_CRM"
    row["canonical_identity_verified"]=True
    assert review(s,a,r)["review_queue"][0]["next_evidence_task"] == "VERIFY_BUDGET_AND_PURCHASING_AUTHORITY"
    row["budget_verified"]=True
    row["icp_intelligence"]={"budget_verified":True}
    assert review(s,a,r)["review_queue"][0]["next_evidence_task"] == "VERIFY_BUYBOX_PRICE_TERMS_AND_PAYMENT_PATH"
    row["commercial_terms_verified"]=True
    row["icp_intelligence"]["commercial_terms_verified"]=True
    assert review(s,a,r)["review_queue"][0]["next_evidence_task"] == "REVIEW_BUYER_CAPACITY_AND_PILOT_RISK_WITH_OWNER"
    assert review(s,a,r)["buyer_activation_authorized"] is False


def test_previous_scout_repeat_cooldown_does_not_trigger_reprobe():
    s,a,r=sources([{"domain":"brand.com"}],[{"domain":"brand.com"}])
    d=review(s,a,r,prior=s)
    row=d["review_queue"][0]
    assert d["research_cooldown_recommendations"] == 1
    assert row["next_evidence_task"] == "COOLDOWN_RESEARCH_REUSE_EXISTING_FIRST_PARTY_EVIDENCE"
    assert d["no_reprobe_execution"] is True


def test_new_verified_reply_prevents_cooldown_suppression():
    s,a,r=sources([{"domain":"brand.com"}],
                   [{"domain":"brand.com","canonical_contact_or_reply_verified":True}])
    d=review(s,a,r,prior=s)
    assert d["review_queue"][0]["research_cooldown_recommended"] is False


def test_conflicting_same_domain_buyer_roles_never_auto_approved():
    s,a,r=sources([
        {"domain":"brand.com","buyer_relationship":"direct_buyer"},
        {"domain":"brand.com","buyer_relationship":"intermediary_or_marketplace"}])
    d=review(s,a,r)
    assert d["review_queue"][0]["next_evidence_task"] == "RESOLVE_SCOUT_AND_FOUNDER_ROLE_CONFLICT"


@pytest.mark.parametrize("mutator", [
    {"scout":{"mode":"SEND"}},
    {"actions":{"outbound_enabled":True}},
    {"registry":{"outbound_authorized":True}},
    {"registry":{"execution_authority":"WRITE"}},
    {"scout":{"generated_at":"2026-10-10T00:00:00+00:00"}},
    {"scout":{"generated_at":"2026-10-19T19:50:00"}},
])
def test_invalid_contracts_hold(mutator):
    s,a,r=sources([],[],[],**mutator)
    with pytest.raises(ValueError):
        review(s,a,r)


def test_source_person_data_never_serialized():
    s,a,r=sources([
        {"domain":"brand.com","first_party_people":[{"name":"Private Person","email":"private@example.com"}]}],
        [{"domain":"brand.com","person_email":"private@example.com"}],
        [{"identity_domains":["brand.com"],"last_inbound_at":NOW_STAMP,
          "gmail_thread_ids":["private-id"],"company":"Private Person"}])
    d=review(s,a,r)
    assert "Private Person" not in json.dumps(d)
    assert "private@example.com" not in json.dumps(d)
    assert "private-id" not in json.dumps(d)
