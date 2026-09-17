from empire_os.buyer_discovery import (
    build_candidate,
    classify_decision_role,
    looks_like_person_name,
    generate_work_email_candidates,
    validate_email_candidates,
    enrich_candidate,
    rank_site_people,
    select_candidates,
)


def test_decision_role_ranking_is_explicit_and_conservative():
    assert classify_decision_role("Founder & CEO") == ("economic_buyer", 1.0)
    assert classify_decision_role("Head of Sales") == ("functional_buyer", 0.8)
    assert classify_decision_role("Marketing Manager") == ("influencer", 0.5)
    assert classify_decision_role("") == ("unknown", 0.0)


def test_candidate_scoring_uses_only_observed_fields():
    row = {
        "id": "p1", "business_name": "Acme Agency", "niche": "marketing agency",
        "metro": "London", "website": "https://acme.test", "phone": "+441234567890",
        "buy_signal_score": 80, "contact_name": "Jane Smith", "contact_title": "Founder",
        "contact_source": "company_site", "entity_id": "e1",
    }
    c = build_candidate(row, entity_id="e1", entity_linked=True)
    assert c.decision_role == "economic_buyer"
    assert c.offer_key == "white_label"
    assert c.company_score > 70
    assert c.mode == "OBSERVE" and c.write_authorized is False


def test_selection_requires_website_and_sorts_by_quality():
    rows = [
        {"id":"a","business_name":"A","website":"https://a.test","phone":"1",
         "niche":"software","metro":"London","buy_signal_score":90,"contact_name":"Ava Stone","contact_title":"CEO","entity_id":"e1"},
        {"id":"b","business_name":"B","website":"","phone":"1",
         "niche":"software","metro":"London","buy_signal_score":100,"contact_name":"Ben Hall","contact_title":"CEO","entity_id":"e2"},
        {"id":"c","business_name":"C","website":"https://c.test","phone":"",
         "niche":"software","metro":"London","buy_signal_score":20,"contact_name":"","contact_title":"","entity_id":""},
    ]
    selected = select_candidates(rows, min_score=50, limit=10)
    assert [c.prospect_id for c in selected] == ["a"]


def test_site_people_are_ranked_and_do_not_invent_identity():
    people = [
        {"name":"Pat Jones","title":"Marketing Manager","email":"pat@x.test"},
        {"name":"Sam Carter","title":"Managing Director","email":"sam@x.test"},
        {"name":"No Title","title":"","email":"none@x.test"},
    ]
    ranked = rank_site_people(people)
    assert ranked[0]["name"] == "Sam Carter"
    assert ranked[0]["decision_role"] == "economic_buyer"
    assert all(p["name"] != "No Title" for p in ranked)


def test_enrichment_prefers_existing_canonical_contact_then_site_person():
    canonical = build_candidate({
        "id":"00000000-0000-0000-0000-000000000001","business_name":"Acme","niche":"software","metro":"London",
        "website":"https://acme.test","contact_name":"Jane Smith","contact_title":"CEO",
        "contact_source":"verified_registry",
    })
    evidence = {"ok":True,"domain":"acme.test","evidence_score":0.8,"pages_checked":[],
                "people":[{"name":"Other Person","title":"Founder","email":"other@acme.test"}],
                "emails":["hello@acme.test"]}
    enriched = enrich_candidate(canonical, evidence)
    assert enriched["decision_maker"]["name"] == "Jane Smith"
    assert enriched["decision_maker"]["source"] == "verified_registry"
    assert enriched["write_authorized"] is False

    site_only = build_candidate({
        "id":"p2","business_name":"Beta","niche":"software","metro":"London",
        "website":"https://beta.test",
    })
    beta_evidence = {**evidence, "domain":"beta.test",
                     "people":[{"name":"Other Person","title":"Founder","email":"other@beta.test"}],
                     "emails":["hello@beta.test"]}
    enriched = enrich_candidate(site_only, beta_evidence)
    assert enriched["decision_maker"]["name"] == "Other Person"
    assert enriched["decision_maker"]["source"] == "website_structured_data"

    mismatch = enrich_candidate(site_only, evidence)
    assert mismatch["decision_maker"] is None
    assert mismatch["contact_email_candidates"] == []
    assert mismatch["site_evidence"]["domain_match"] is False


def test_verified_contact_gate_requires_named_authority_and_non_role_email():
    from types import SimpleNamespace
    from empire_os.buyer_discovery import verify_contact_plan

    class Validator:
        def validate(self, email):
            if email.startswith("info@"):
                return SimpleNamespace(email=email,is_valid=False,confidence=0.0,
                    is_role_address=True,is_disposable=False,has_mx=True,smtp_accepts=False)
            return SimpleNamespace(email=email,is_valid=True,confidence=0.95,
                is_role_address=False,is_disposable=False,has_mx=True,smtp_accepts=True)

    enriched = {
        "decision_maker":{"name":"Jane Smith","title":"CEO","decision_score":1.0},
        "contact_email_candidates":["info@acme.test","jane@acme.test"],
    }
    plan = verify_contact_plan(enriched, validator=Validator())
    assert plan["outreach_ready"] is True
    assert plan["preferred_email"] == "jane@acme.test"
    assert plan["write_authorized"] is False

    no_person = verify_contact_plan(
        {"decision_maker":None,"contact_email_candidates":["jane@acme.test"]},
        validator=Validator(),
    )
    assert no_person["outreach_ready"] is False


def test_outbound_plan_requires_verified_contact_optout_and_postal_footer():
    from empire_os.buyer_discovery import build_outbound_intent_plan
    candidate = build_candidate({
        "id":"00000000-0000-0000-0000-000000000001","business_name":"Acme","niche":"software","metro":"London",
        "website":"https://acme.test","contact_name":"Jane Smith","contact_title":"CEO",
    })
    contact = {"outreach_ready":True,"preferred_email":"jane@acme.test"}
    body = "Hi Jane. Relevant revenue idea. Reply to opt out. 10 Example Street, London."
    plan = build_outbound_intent_plan(
        candidate, contact, subject="Revenue idea", body_text=body,
        proposed_by="planner", expires_at="2026-09-18T18:00:00+00:00",
        idempotency_key="buyer:0001:001", postal_address="10 Example Street, London",
    )
    assert plan["rpc"] == "propose_outbound_intent"
    assert plan["params"]["p_recipient"] == "jane@acme.test"
    assert plan["params"]["p_offer_key"] == "high_ticket"
    assert plan["write_authorized"] is False

    import pytest
    with pytest.raises(ValueError, match="opt-out"):
        build_outbound_intent_plan(
            candidate, contact, subject="x", body_text="No footer 10 Example Street, London",
            proposed_by="planner", expires_at="2026-09-18T18:00:00+00:00",
            idempotency_key="buyer:0001:002", postal_address="10 Example Street, London",
        )


def test_scraped_page_labels_cannot_become_decision_makers():
    from empire_os.buyer_discovery import looks_like_person_name
    for value in ("Maintenance Membership", "Pricing Guide", "Award multiple"):
        assert looks_like_person_name(value) is False
        candidate = build_candidate({
            "id":"00000000-0000-0000-0000-000000000099",
            "business_name":"Example Co", "website":"https://example.test",
            "niche":"hvac", "metro":"Atlanta", "buy_signal_score":100,
            "contact_name":value, "contact_title":"Founder",
        })
        assert candidate.contact_name == ""
        assert candidate.contact_title == ""
        assert candidate.decision_role == "unknown"
        assert candidate.evidence["raw_contact_name_present"] is True
        assert candidate.evidence["contact_personhood_valid"] is False


def test_personhood_guard_rejects_live_scrape_fragments():
    bad = [
        "Lorem Ipsum", "himself came", "ship Jonathan", "engineer who",
        "Owner Nathan", "was exceptional", "does not", "who needed",
        "ial Club", "through each", "After graduating", "was very",
    ]
    for value in bad:
        assert looks_like_person_name(value) is False, value
    good = ["Frank Stilley", "Christina Doe", "Ronald Moss", "Eric Aultz",
            "Sam Shukuri", "Clay Winter", "Mason Hoover", "Peter Reed",
            "Mary-Jane O'Connor", "J. R. Smith"]
    for value in good:
        assert looks_like_person_name(value) is True, value


def test_email_pattern_generation_is_candidate_only_and_domain_bound():
    values = generate_work_email_candidates("Jane Smith", "https://www.acme.co.uk/about")
    assert values[0] == "jane.smith@acme.co.uk"
    assert "jsmith@acme.co.uk" in values
    assert generate_work_email_candidates("Pricing Guide", "https://acme.co.uk") == []


def test_email_candidate_validation_preserves_evidence_level():
    class Result:
        def __init__(self, valid, mx, smtp=False, confidence=0.0):
            self.is_valid=valid; self.has_mx=mx; self.smtp_accepts=smtp
            self.confidence=confidence; self.is_role_address=False; self.is_disposable=False
    class Validator:
        def validate(self, email):
            if email.startswith("jane.smith"):
                return Result(True, True, False, 0.75)
            if email.startswith("jsmith"):
                return Result(True, True, True, 0.95)
            return Result(False, True, False, 0.5)
    checked = validate_email_candidates([
        "jane.smith@acme.co.uk","jsmith@acme.co.uk","x@acme.co.uk"
    ], Validator())
    assert checked[0]["verification_state"] == "mx_valid"
    assert checked[1]["verification_state"] == "smtp_valid"
    assert checked[2]["verification_state"] == "mx_observed"
    strict = validate_email_candidates(["jane.smith@acme.co.uk","jsmith@acme.co.uk"], Validator(), require_smtp=True)
    assert [x["email"] for x in strict] == ["jsmith@acme.co.uk"]
