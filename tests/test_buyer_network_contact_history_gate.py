import json

from empire_os.buyer_network_contact_history_gate import load_context, review


def test_missing_history_fails_closed(tmp_path):
    result = review("buyer.com", load_context(tmp_path/"missing.json", tmp_path/"missing2.json"))
    assert result["state"] == "SOURCE_UNAVAILABLE"
    assert result["outbound_authorized"] is False


def test_prior_contact_wins_over_discovery_score(tmp_path):
    context = make_context(tmp_path, [{"entity_key":"buyer.com", "identity_domains": ["www.buyer.com"],
                                      "gmail_thread_ids": ["thread"], "last_outbound_at": "2026-09-25"}])
    item = review("www.buyer.com", context)
    assert item["state"] == "ALREADY_CONTACTED"
    assert item["thread_count"] == 1
    assert not item["history_verified_complete"]


def test_founder_form_no_duplicate(tmp_path):
    context = make_context(tmp_path, [{"entity_key":"polyares.com", "identity_domains":["polyares.com"]}],
                           [{"domain":"polyares.com", "channel":"website_contact_form"}])
    assert review("polyares.com", context)["state"] == "FOUNDER_FORM_SUBMITTED"


def test_hard_bounce_hold(tmp_path):
    context = make_context(tmp_path, [{"entity_key":"webuycalls.com", "bounced_addresses":["team@webuycalls.com"]}])
    assert review("webuycalls.com", context)["state"] == "DELIVERY_HOLD"


def test_opt_out_beats_contact(tmp_path):
    context = make_context(tmp_path, [{"entity_key":"buyer.com", "do_not_pursue":True,
                                      "gmail_thread_ids":["thread"]}])
    item = review("buyer.com", context)
    assert item["state"] == "DO_NOT_PURSUE"
    assert item["next_action"] == "NO_CONTACT"


def test_unknown_never_marked_fresh_or_new_contact(tmp_path):
    context = make_context(tmp_path, [])
    assert review("uncertain.com", context)["state"] == "UNKNOWN_HISTORY"
    assert review("uncertain.com", context)["outbound_authorized"] is False


def make_context(tmp_path, relationships, observations=()):
    a,b = tmp_path/"registry.json",tmp_path/"forms.json"
    a.write_text(json.dumps({"schema_version":"empire.commercial_relationship_registry.v1",
                             "gmail_snapshot_fresh":False,"relationships":relationships}))
    b.write_text(json.dumps({"schema_version":"empire.founder_reported_external_contacts.v1",
                             "observations":list(observations)}))
    return load_context(a,b)


def test_reply_from_real_partner_is_not_hidden_by_one_bounced_address(tmp_path):
    context = make_context(tmp_path, [{
        "entity_key": "validated",
        "identity_domains": ["homeservicesleadgroup.com"],
        "gmail_thread_ids": ["verified-thread"],
        "last_inbound_at": "2026-10-07",
        "bounced_addresses": ["info@homeservicesleadgroup.com"],
    }])
    item = review("homeservicesleadgroup.com", context)
    assert item["state"] == "EXISTING_CONVERSATION_PARTIAL_BOUNCE"
    assert "AVOID_BOUNCED_ADDRESS" in item["next_action"]
    assert item["outbound_authorized"] is False


def test_provider_dsn_overrides_workspace_sent_mail_and_holds_exact_failed_address(tmp_path):
    import os
    from empire_os.buyer_network_contact_history_gate import read_confirmed_delivery_failures

    ctx=make_context(tmp_path,[])
    found=tmp_path/"multiformat_publisher_founder_review_latest.json"
    found.write_text(json.dumps({
        "schema_version":"empire.buyer_multiformat_founder_review.v1",
        "companies":[{
            "domain":"getmapleleads.com",
            "provider_delivery_failed":True,
            "provider_delivery_failure_code":"550_NO_SUCH_USER_HERE",
            "gmail_sent_message_id":"1a1609763ff99e96",
            "gmail_sent_thread_id":"1a1608b157033429",
            "provider_delivery_failure_message_id":"1a1609809ea130ee",
            "delivery_failed_original_sent_message_id":"1a1609763ff99e96",
            "delivery_failed_recipient":"partners@getmapleleads.com",
            "verified_public_contact":"partners@getmapleleads.com",
            "provider_send_confirmed":True,
            "provider_delivery_verified":False,
            "outbound_authorized":False,
        }],
    }))
    os.chmod(found,0o600)
    ctx=load_context(tmp_path/"registry.json",tmp_path/"forms.json",
                     tmp_path/"unavailable_workspace.json")
    # Previously confirmed Workspace SENT must not override the later DSN.
    ctx["workspace_sent"]={"getmapleleads.com":{"last_sent_at":"2026-10-21"}}
    r=review("getmapleleads.com",ctx)
    assert r["state"]=="DELIVERY_HOLD"
    assert r["confirmed_hard_bounce"] is True
    assert r["confirmed_hard_bounce_code"]=="550_NO_SUCH_USER_HERE"
    assert r["outbound_authorized"] is False
    assert "NO_RETRY" in r["next_action"]
    assert review("otherbuyer.com",ctx)["state"]=="UNKNOWN_HISTORY"

    # The evidence must be private; otherwise every contact is held.
    os.chmod(found,0o644)
    ctx=load_context(tmp_path/"registry.json",tmp_path/"forms.json",
                     tmp_path/"unavailable_workspace.json")
    assert ctx["available"] is False
    assert review("getmapleleads.com",ctx)["state"]=="SOURCE_UNAVAILABLE"


def test_delivery_receipt_requires_exact_original_send_and_verified_recipient(tmp_path):
    import os
    import pytest
    from empire_os.buyer_network_contact_history_gate import read_confirmed_delivery_failures
    p=tmp_path/"multiformat_publisher_founder_review_latest.json"
    base={
        "domain":"getmapleleads.com",
        "provider_delivery_failed":True,
        "provider_delivery_failure_code":"550_NO_SUCH_USER_HERE",
        "gmail_sent_message_id":"1a1609763ff99e96",
        "provider_delivery_failure_message_id":"1a1609809ea130ee",
        "delivery_failed_original_sent_message_id":"1a1609763ff99e96",
        "delivery_failed_recipient":"partners@getmapleleads.com",
        "verified_public_contact":"partners@getmapleleads.com",
        "provider_send_confirmed":True,
        "provider_delivery_verified":False,
        "outbound_authorized":False,
    }
    for variant in [
        {**base,"delivery_failed_recipient":"other@getmapleleads.com"},
        {**base,"delivery_failed_original_sent_message_id":"1a1609763ff99e97"},
        {**base,"provider_delivery_failure_code":"550_UNVERIFIED"},
        {**base,"outbound_authorized":True},
        {**base,"gmail_sent_message_id":"bogus"},
    ]:
        p.write_text(json.dumps({
            "schema_version":"empire.buyer_multiformat_founder_review.v1",
            "companies":[variant],
        }))
        os.chmod(p,0o600)
        with pytest.raises(ValueError,match="FOUNDER_DELIVERY_PROOF_INVALID"):
            read_confirmed_delivery_failures(p)


def test_confirmed_bounce_does_not_override_proven_inbound_conversation(tmp_path):
    import os
    p=tmp_path/"multiformat_publisher_founder_review_latest.json"
    p.write_text(json.dumps({
        "schema_version":"empire.buyer_multiformat_founder_review.v1",
        "companies":[{
            "domain":"getmapleleads.com",
            "provider_delivery_failed":True,
            "provider_delivery_failure_code":"550_NO_SUCH_USER_HERE",
            "gmail_sent_message_id":"1a1609763ff99e96",
            "provider_delivery_failure_message_id":"1a1609809ea130ee",
            "delivery_failed_original_sent_message_id":"1a1609763ff99e96",
            "delivery_failed_recipient":"partners@getmapleleads.com",
            "verified_public_contact":"partners@getmapleleads.com",
            "provider_send_confirmed":True,
            "provider_delivery_verified":False,
            "outbound_authorized":False,
        }],
    }))
    os.chmod(p,0o600)
    make_context(tmp_path,[
        {"entity_key":"getmapleleads.com","last_inbound_at":"2026-10-22T10:00:00+00:00",
         "identity_domains":["getmapleleads.com"]},
    ])
    ctx=load_context(tmp_path/"registry.json",tmp_path/"forms.json",
                     tmp_path/"unavailable_workspace.json")
    result=review("getmapleleads.com",ctx)
    assert result["state"]=="EXISTING_CONVERSATION"
    assert result["confirmed_hard_bounce"] is True
    assert result["outbound_authorized"] is False
