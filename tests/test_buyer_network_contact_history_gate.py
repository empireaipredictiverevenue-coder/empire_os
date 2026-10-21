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
