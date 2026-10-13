"""Authenticated partner thread must not be mistaken for software-buyer demand."""
import json
from copy import deepcopy
from pathlib import Path

import pytest

from empire_os.commercial_relationship_registry import RelationshipEvidenceError
from scripts.reconcile_buyer_email_relationships import annotate_new_engaged_commercial_roles


TID = "1a134dc80c6a49e7"
DOMAIN = "myjobquote.co.uk"
EVIDENCE = Path("docs/commercial/ENGAGED_AFFILIATE_PARTNER_ROLE_EVIDENCE_20261013.json")


def queue(thread=TID, reply=TID, domain=DOMAIN):
    return {
        "new_engaged_buyer_identity_review_queue": [{
            "thread_id": thread,
            "domain": domain,
            "last_buyer_reply_id": reply,
            "status": "REVIEW_IDENTITY_NO_SEND",
            "reported_constraint": None,
            "source": "EXACT_TWO_WAY_DMARC_ALIGNED_EMAIL_REPORTED",
            "outbound_authorized": False,
            "execution_authority": "NONE",
        }],
        "new_engaged_buyer_identity_review_count": 1,
    }


def install(tmp_path, modifier=None):
    doc = tmp_path / EVIDENCE
    doc.parent.mkdir(parents=True, exist_ok=True)
    fixture = json.loads(EVIDENCE.read_text())
    if modifier:
        modifier(fixture)
    doc.write_text(json.dumps(fixture))
    return doc


def test_exact_affiliate_reply_routes_to_referral_review_without_buying_authority(tmp_path):
    install(tmp_path)
    value = queue()
    annotate_new_engaged_commercial_roles(value, root=tmp_path)
    assert value["new_engaged_buyer_identity_review_count"] == 0
    assert value["new_engaged_publisher_supply_review_count"] == 0
    assert value["new_engaged_affiliate_referral_review_count"] == 1
    record = value["new_engaged_affiliate_referral_review_queue"][0]
    assert record["company"] == "MyJobQuote"
    assert record["thread_id"] == TID
    assert record["last_reply_id"] == TID
    assert record["role_hypothesis"] == "AFFILIATE_REFERRAL_PROGRAMME_NOT_EMPIRE_SOFTWARE_CUSTOMER"
    assert record["next_action"] == "AWAIT_AFFILIATE_TERMS_NO_REPEAT_EMAIL"
    assert all(record[name] is False for name in (
        "partner_source_approval_verified", "referral_terms_approved",
        "traffic_activated", "buyer_software_demand_verified", "outbound_authorized",
    ))
    assert record["execution_authority"] == "NONE"
    assert value["new_engaged_commercial_role_classification"]["affiliate_referral_hypotheses"] == 1


@pytest.mark.parametrize("change", [
    {"thread": "aaaaaaaaaaaaaaaa"},
    {"domain": "different.example"},
])
def test_no_automatic_role_inference_from_domain_or_partial_reply(tmp_path, change):
    install(tmp_path)
    value = queue(**change)
    before = deepcopy(value["new_engaged_buyer_identity_review_queue"])
    annotate_new_engaged_commercial_roles(value, root=tmp_path)
    assert value["new_engaged_buyer_identity_review_queue"] == before
    assert value["new_engaged_buyer_identity_review_count"] == 1
    assert value["new_engaged_affiliate_referral_review_count"] == 0
    assert value["new_engaged_publisher_supply_review_count"] == 0


def test_new_authenticated_reply_in_same_bound_thread_preserves_role(tmp_path):
    install(tmp_path)
    value = queue(reply="bbbbbbbbbbbbbbbb")
    annotate_new_engaged_commercial_roles(value, root=tmp_path)
    assert value["new_engaged_buyer_identity_review_count"] == 0
    assert value["new_engaged_affiliate_referral_review_count"] == 1
    record = value["new_engaged_affiliate_referral_review_queue"][0]
    assert record["last_reply_id"] == "bbbbbbbbbbbbbbbb"
    assert record["thread_id"] == TID
    assert record["outbound_authorized"] is False
    assert record["referral_terms_approved"] is False


def test_absent_role_source_preserves_unlinked_review(tmp_path):
    value = queue()
    annotate_new_engaged_commercial_roles(value, root=tmp_path)
    assert value["new_engaged_buyer_identity_review_count"] == 1
    assert value["new_engaged_affiliate_referral_review_count"] == 0


@pytest.mark.parametrize("modifier", [
    lambda d: d["items"][0].update(traffic_activated=True),
    lambda d: d["items"][0].update(buyer_software_demand_verified=True),
    lambda d: d["items"][0].update(referral_terms_approved=True),
    lambda d: d["items"][0].update(outbound_authorized=True),
    lambda d: d["items"][0].update(role="VERIFIED_SOFTWARE_BUYER"),
    lambda d: d.update(schema_version="untrusted.v2"),
    lambda d: d["items"].append(deepcopy(d["items"][0])),
])
def test_malformed_or_authority_claiming_role_evidence_fails_closed(tmp_path, modifier):
    install(tmp_path, modifier)
    value = queue()
    before = deepcopy(value)
    with pytest.raises(RelationshipEvidenceError):
        annotate_new_engaged_commercial_roles(value, root=tmp_path)
    assert value == before


def test_existing_publisher_supply_role_is_preserved(tmp_path):
    install(tmp_path)
    supply = tmp_path / "docs/commercial/PUBLISHER_SUPPLY_RECRUITMENT_EVIDENCE_20261010.json"
    supply.write_text(json.dumps({
        "schema_version": "empire.publisher_supply_recruitment_evidence.v1",
        "items": [{"role": "TRAFFIC_SUPPLY_HYPOTHESIS", "domain": "roofpitch.net", "company": "RoofPitch.net"}],
    }))
    value = queue()
    value["new_engaged_buyer_identity_review_queue"].append({
        **queue()["new_engaged_buyer_identity_review_queue"][0],
        "thread_id": "cccccccccccccccc", "domain": "roofpitch.net",
        "last_buyer_reply_id": "dddddddddddddddd",
    })
    value["new_engaged_buyer_identity_review_count"] = 2
    annotate_new_engaged_commercial_roles(value, root=tmp_path)
    assert value["new_engaged_affiliate_referral_review_count"] == 1
    assert value["new_engaged_publisher_supply_review_count"] == 1
    assert value["new_engaged_buyer_identity_review_count"] == 0
