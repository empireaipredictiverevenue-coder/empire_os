from empire_os.buyer_discovery import (
    accepted_acquisition_website,
    build_buyer_readiness_dossier,
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


def test_directory_website_is_not_first_party_buyer_evidence():
    row = {
        "id": "dir-1",
        "business_name": "Directory Roofing",
        "website": "https://www.bbb.org/us/tx/austin/profile/roofing-contractors/example",
        "phone": "5125550101",
        "niche": "roofing",
        "metro": "Austin, TX",
        "buy_signal_score": 100,
        "contact_name": "Jane Smith",
        "contact_title": "Owner",
        "entity_id": "e-dir",
    }
    candidate = build_candidate(
        row,
        entity_id="e-dir",
        entity_linked=True,
    )
    assert candidate.website == ""
    assert candidate.evidence["has_website"] is False
    assert candidate.evidence["directory_website_rejected"] is True
    assert select_candidates([row], min_score=0, limit=10) == []
    assert generate_work_email_candidates(
        "Jane Smith",
        row["website"],
    ) == []


def accepted_acquisition_evidence(
    website="https://www.allstarroofingtexas.com/",
    *,
    accepted=True,
    source_role="identity_or_direct",
):
    return {
        "quality": {
            "accepted": accepted,
            "confidence": 100,
            "source_role": source_role,
        },
        "raw": {
            "business_website": website,
            "osm_tags": {"website": website},
        },
    }


def test_accepted_acquisition_site_is_first_party_fallback():
    evidence = accepted_acquisition_evidence()
    row = {
        "id": "acq-1",
        "business_name": "All Star Roofing",
        "website": "",
        "phone": "+1-512-477-7827",
        "niche": "roofing",
        "metro": "Austin, TX",
        "buy_signal_score": 80,
        "entity_id": "e-acq",
        "_acquisition_evidence": evidence,
    }
    candidate = build_candidate(
        row,
        entity_id="e-acq",
        entity_linked=True,
    )
    assert accepted_acquisition_website(evidence) == (
        "https://www.allstarroofingtexas.com/"
    )
    assert candidate.website == "https://www.allstarroofingtexas.com/"
    assert candidate.evidence["website_source"] == "accepted_acquisition"
    assert candidate.evidence["acquisition_website_accepted"] is True
    assert candidate.evidence["has_website"] is True
    assert [item.prospect_id for item in select_candidates(
        [row], min_score=0, limit=10
    )] == ["acq-1"]


def test_acquisition_site_fallback_is_fail_closed():
    for evidence in (
        accepted_acquisition_evidence(accepted=False),
        accepted_acquisition_evidence(source_role="discovery_only"),
        accepted_acquisition_evidence(
            website="https://www.bbb.org/us/tx/austin/example"
        ),
        {"quality": {"accepted": True, "source_role": "identity_or_direct"}},
    ):
        assert accepted_acquisition_website(evidence) == ""

    row = {
        "id": "acq-bad",
        "business_name": "Bad Acquisition",
        "website": "",
        "niche": "roofing",
        "metro": "Austin, TX",
        "_acquisition_evidence": accepted_acquisition_evidence(
            accepted=False
        ),
    }
    assert build_candidate(row).website == ""
    assert select_candidates([row], min_score=0, limit=10) == []


def test_canonical_first_party_site_precedes_acquisition_fallback():
    row = {
        "id": "canonical-wins",
        "business_name": "Canonical Co",
        "website": "https://canonical.example",
        "niche": "roofing",
        "metro": "Austin, TX",
        "_acquisition_evidence": accepted_acquisition_evidence(
            website="https://acquired.example"
        ),
    }
    candidate = build_candidate(row)
    assert candidate.website == "https://canonical.example"
    assert candidate.evidence["website_source"] == "canonical_prospect"
    assert candidate.evidence["acquisition_website_accepted"] is False


def test_directory_canonical_site_can_fall_back_to_accepted_acquisition():
    row = {
        "id": "directory-fallback",
        "business_name": "Directory Fallback",
        "website": "https://www.bbb.org/example",
        "niche": "roofing",
        "metro": "Austin, TX",
        "_acquisition_evidence": accepted_acquisition_evidence(
            website="https://firstparty.example"
        ),
    }
    candidate = build_candidate(row)
    assert candidate.website == "https://firstparty.example"
    assert candidate.evidence["directory_website_rejected"] is True
    assert candidate.evidence["acquisition_website_accepted"] is True


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
        "contact_candidates":[
            {"email":"info@acme.test","source":"site_observed","bound_to_decision_maker":False},
            {"email":"jane@acme.test","source":"person_structured_data","bound_to_decision_maker":True},
        ],
    }
    plan = verify_contact_plan(enriched, validator=Validator())
    assert plan["review_ready"] is True
    assert plan["outreach_ready"] is True
    assert plan["preferred_email"] == "jane@acme.test"
    assert plan["write_authorized"] is False

    no_person = verify_contact_plan(
        {"decision_maker":None,"contact_candidates":[{"email":"jane@acme.test","source":"person_structured_data","bound_to_decision_maker":True}]},
        validator=Validator(),
    )
    assert no_person["review_ready"] is False
    assert no_person["outreach_ready"] is False

    generic_only = verify_contact_plan(
        {"decision_maker":{"name":"Jane Smith","title":"CEO","decision_score":1.0},
         "contact_candidates":[{"email":"office@acme.test","source":"site_observed","bound_to_decision_maker":False}]},
        validator=Validator(),
    )
    assert generic_only["review_ready"] is False
    assert generic_only["outreach_ready"] is False
    assert generic_only["preferred_email"] is None


def test_candidate_review_and_reviewed_outbound_plans_are_separate():
    import pytest
    from empire_os.buyer_discovery import (
        build_candidate_review_plan, build_reviewed_outbound_intent_plan
    )
    candidate = build_candidate({
        "id":"00000000-0000-0000-0000-000000000001","business_name":"Acme","niche":"software","metro":"London",
        "website":"https://acme.test","contact_name":"Jane Smith","contact_title":"CEO",
    })
    contact = {
        "review_ready":True,"outreach_ready":True,"preferred_email":"jane@acme.test",
        "decision_maker":{"name":"Jane Smith","title":"CEO","decision_score":1.0,"decision_role":"economic_buyer"},
        "verified_contacts":[{"email":"jane@acme.test","is_valid":True}],
    }
    review = build_candidate_review_plan(candidate, contact, idempotency_key="buyer:0001:review")
    assert review["rpc"] == "propose_buyer_candidate_review"
    assert review["params"]["p_contact_email"] == "jane@acme.test"
    assert review["params"]["p_offer_key"] == "high_ticket"
    assert review["params"]["p_evidence"]["review_ready"] is True
    assert review["params"]["p_evidence"]["outreach_ready"] is True
    assert review["params"]["p_evidence"]["business_name"] == "Acme"
    assert review["params"]["p_evidence"]["niche"] == "software"
    assert review["params"]["p_evidence"]["metro"] == "London"
    assert review["params"]["p_evidence"]["website"] == "https://acme.test"
    assert review["params"]["p_evidence"]["contact_source"] is None

    sourced_contact = {
        **contact,
        "decision_maker": {
            **contact["decision_maker"],
            "source": "website_structured_data",
        },
        "verified_contacts": [{
            "email": "jane@acme.test",
            "is_valid": True,
            "source": "person_structured_data",
        }],
    }
    sourced = build_candidate_review_plan(
        candidate, sourced_contact, idempotency_key="buyer:0001:sourced"
    )
    assert sourced["params"]["p_evidence"]["contact_source"] == "official_site"
    assert sourced["params"]["p_evidence"]["decision_source"] == "website_structured_data"
    preferred = sourced["params"]["p_evidence"]["verified_contacts"][0]
    assert preferred["source"] == "official_site"
    assert preferred["source_detail"] == "person_structured_data"
    assert review["write_authorized"] is False

    body = "Hi Jane. Relevant revenue idea. Reply to opt out. 10 Example Street, London."
    outbound = build_reviewed_outbound_intent_plan(
        "00000000-0000-0000-0000-000000000099",
        subject="Revenue idea", body_text=body, proposed_by="planner",
        expires_at="2026-09-18T18:00:00+00:00", idempotency_key="buyer:0001:outbound",
        postal_address="10 Example Street, London",
    )
    assert outbound["rpc"] == "propose_reviewed_outbound_intent"
    assert outbound["params"]["p_review_id"] == "00000000-0000-0000-0000-000000000099"
    assert outbound["write_authorized"] is False

    with pytest.raises(ValueError, match="opt-out"):
        build_reviewed_outbound_intent_plan(
            "00000000-0000-0000-0000-000000000099", subject="x",
            body_text="No footer 10 Example Street, London", proposed_by="planner",
            expires_at="2026-09-18T18:00:00+00:00", idempotency_key="buyer:0001:bad",
            postal_address="10 Example Street, London",
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


def test_generated_pattern_requires_smtp_before_binding():
    from types import SimpleNamespace
    from empire_os.buyer_discovery import merge_generated_contact_evidence, verify_contact_plan
    enriched={
        "decision_maker":{"name":"Jane Smith","title":"CEO","decision_score":1.0},
        "contact_candidates":[],
    }
    merged=merge_generated_contact_evidence(enriched,[
        {"email":"jane.smith@acme.test","verification_state":"mx_valid"},
        {"email":"jsmith@acme.test","verification_state":"smtp_valid"},
    ])
    assert [x["email"] for x in merged["contact_candidates"]] == ["jsmith@acme.test"]
    class Validator:
        def validate(self,email):
            return SimpleNamespace(email=email,is_valid=True,confidence=0.95,is_role_address=False,is_disposable=False,has_mx=True,smtp_accepts=True)
    plan=verify_contact_plan(merged,validator=Validator())
    assert plan["outreach_ready"] is True
    assert plan["preferred_email"] == "jsmith@acme.test"


def test_current_official_role_conflict_requires_review():
    from types import SimpleNamespace
    from empire_os.buyer_discovery import reconcile_decision_maker, verify_contact_plan
    candidate = build_candidate({
        "id":"00000000-0000-0000-0000-000000000777","business_name":"Quality Exteriors",
        "niche":"roofing","metro":"Austin","website":"https://quality.example",
        "contact_name":"Peter Reed","contact_title":"Owner","contact_source":"public_website",
    })
    official=[{"name":"Peter Reed","title":"Project Manager","email":"peter@quality.example"}]
    rec=reconcile_decision_maker(candidate,official)
    assert rec["status"] == "role_conflict"
    assert rec["review_required"] is True
    assert rec["decision_maker"]["decision_role"] == "influencer"
    class Validator:
        def validate(self,email):
            return SimpleNamespace(email=email,is_valid=True,confidence=0.95,is_role_address=False,
                                   is_disposable=False,has_mx=True,smtp_accepts=True)
    enriched={"decision_maker":rec["decision_maker"],"decision_reconciliation":rec,
              "contact_candidates":[{"email":"peter@quality.example","source":"person_structured_data",
                                      "bound_to_decision_maker":True}]}
    assert verify_contact_plan(enriched,validator=Validator())["outreach_ready"] is False


def test_current_official_equivalent_authority_confirms_candidate():
    from empire_os.buyer_discovery import reconcile_decision_maker
    candidate=build_candidate({
        "id":"00000000-0000-0000-0000-000000000778","business_name":"Acme",
        "website":"https://acme.example","contact_name":"Jane Smith","contact_title":"Founder",
    })
    rec=reconcile_decision_maker(candidate,[{"name":"Jane Smith","title":"CEO","email":"jane@acme.example"}])
    assert rec["status"] == "confirmed"
    assert rec["review_required"] is False
    assert rec["decision_maker"]["decision_role"] == "economic_buyer"


def test_public_web_contact_binding_requires_explicit_identity_and_role_corroboration():
    from empire_os.buyer_discovery import merge_public_web_contact_evidence
    enriched={
        "decision_maker":{"name":"Hugo Guerra","title":"Owner","decision_score":1.0},
        "contact_candidates":[],
    }
    accepted=merge_public_web_contact_evidence(enriched,[{
        "name":"Hugo Guerra","email":"hugo@example.com",
        "source_url":"https://directory.example/hugo","source_kind":"public_business_directory",
        "role_corroborated":True,
    }])
    assert accepted["public_web_evidence_accepted"] == 1
    assert accepted["contact_candidates"][0]["bound_to_decision_maker"] is True

    rejected=merge_public_web_contact_evidence(enriched,[
        {"name":"Other Person","email":"hugo@example.com","source_url":"https://x.example/a",
         "source_kind":"public_business_directory","role_corroborated":True},
        {"name":"Hugo Guerra","email":"hugo@example.com","source_url":"https://x.example/b",
         "source_kind":"public_business_directory","role_corroborated":False},
        {"name":"Hugo Guerra","email":"hugo@example.com","source_url":"https://x.example/c",
         "source_kind":"social_profile","role_corroborated":True},
    ])
    assert rejected["public_web_evidence_accepted"] == 0
    assert rejected["contact_candidates"] == []


def test_site_observed_exact_first_name_can_be_review_bound_but_not_send_ready():
    from types import SimpleNamespace
    from empire_os.buyer_discovery import verify_contact_plan
    candidate = build_candidate({
        "id":"75c4d15b-3b1d-4779-8917-c14a6b624403",
        "business_name":"Prodigy Restoration", "niche":"restoration", "metro":"Oklahoma City",
        "website":"https://prodigyrestoration.com/", "contact_name":"Matthew Maloy",
        "contact_title":"Founder", "contact_source":"public_website",
    })
    evidence={"ok":True,"domain":"prodigyrestoration.com","evidence_score":1.0,"pages_checked":[],
              "people":[],"emails":["matthew@prodigyrestoration.com","info@prodigyrestoration.com"]}
    enriched=enrich_candidate(candidate,evidence)
    bound=[x for x in enriched["contact_candidates"] if x["bound_to_decision_maker"]]
    assert bound == [{"email":"matthew@prodigyrestoration.com",
                      "source":"site_observed_first_name_match",
                      "bound_to_decision_maker":True}]
    class Validator:
        def validate(self,email):
            if email.startswith("info@"):
                return SimpleNamespace(email=email,is_valid=False,confidence=0.0,is_role_address=True,is_disposable=False,has_mx=False,smtp_accepts=False)
            return SimpleNamespace(email=email,is_valid=True,confidence=0.75,is_role_address=False,is_disposable=False,has_mx=True,smtp_accepts=False)
    plan=verify_contact_plan(enriched,validator=Validator())
    assert plan["review_ready"] is True
    assert plan["outreach_ready"] is False
    assert plan["preferred_email"] == "matthew@prodigyrestoration.com"


def test_recent_exact_public_record_can_support_outreach_without_smtp():
    from types import SimpleNamespace
    from empire_os.buyer_discovery import merge_public_web_contact_evidence, verify_contact_plan
    candidate = build_candidate({
        "id":"f1100b66-90bb-49d7-8bdd-bdb54bd055cb","business_name":"Silverado Construction Services",
        "niche":"general contractor","metro":"Dallas-Fort Worth","website":"http://www.silveradoconstruct.com/",
        "contact_name":"Jake Montgomery","contact_title":"Founder","contact_source":"public_website",
    })
    enriched = {"decision_maker":{"name":"Jake Montgomery","title":"Founder","decision_score":1.0},
                "contact_candidates":[],"decision_reconciliation":{"review_required":False}}
    enriched = merge_public_web_contact_evidence(enriched,[{
        "name":"Jake Montgomery","email":"jake@silveradoconstruct.com",
        "source_url":"https://example.gov/permit-record","source_kind":"public_government_record",
        "role_corroborated":True,"direct_publication":True,"published_at":"2025-01-06",
    }])
    class Validator:
        def validate(self,email):
            return SimpleNamespace(email=email,is_valid=True,confidence=0.75,is_role_address=False,
                is_disposable=False,has_mx=True,smtp_accepts=False)
    plan = verify_contact_plan(enriched, validator=Validator())
    assert plan["review_ready"] is True
    assert plan["outreach_ready"] is True
    assert plan["preferred_email"] == "jake@silveradoconstruct.com"


def test_stale_exact_public_record_cannot_be_bound_as_recent_evidence():
    from empire_os.buyer_discovery import merge_public_web_contact_evidence
    enriched={"decision_maker":{"name":"Jake Montgomery","title":"Founder","decision_score":1.0},"contact_candidates":[]}
    merged=merge_public_web_contact_evidence(enriched,[{
        "name":"Jake Montgomery","email":"jake@silveradoconstruct.com",
        "source_url":"https://example.gov/old-record","source_kind":"public_government_record",
        "role_corroborated":True,"direct_publication":True,"published_at":"2019-01-01",
    }])
    assert merged["public_web_evidence_accepted"] == 0
    assert merged["contact_candidates"] == []


def test_public_web_email_named_for_different_person_cannot_bind_to_decision_maker():
    from empire_os.buyer_discovery import merge_public_web_contact_evidence
    enriched = {
        "decision_maker": {"name":"Luis Mondragon","title":"Founder","decision_score":1.0},
        "contact_candidates": [],
    }
    merged = merge_public_web_contact_evidence(enriched,[{
        "name":"Jorge Mondragon",
        "email":"office@mondragonac.com",
        "source_url":"https://mondragonac.com/jose-luis-mondragon/",
        "source_kind":"official_site",
        "role_corroborated":True,
        "direct_publication":True,
    }])
    assert merged["public_web_evidence_accepted"] == 0
    assert merged["contact_candidates"] == []


def test_public_decision_maker_requires_corroborated_identity_and_role():
    from types import SimpleNamespace
    from empire_os.buyer_discovery import (
        merge_public_decision_maker_evidence,
        verify_contact_plan,
    )

    enriched = {
        "decision_maker": None,
        "contact_candidates": [],
    }
    merged = merge_public_decision_maker_evidence(enriched, [
        {
            "name": "Terry Paris",
            "title": "Owner",
            "source_url": "https://www.bbb.org/example/all-star-roofing",
            "source_kind": "public_business_directory",
            "business_identity_correlated": True,
        },
        {
            "name": "Terry Paris",
            "title": "Owner",
            "source_url": "https://www.buildzoom.com/example/all-star-roofing",
            "source_kind": "public_business_directory",
            "business_identity_correlated": True,
        },
    ])

    assert merged["decision_maker"]["name"] == "Terry Paris"
    assert merged["decision_maker"]["decision_role"] == "economic_buyer"
    assert merged["decision_maker"]["source"] == "public_web_corroborated"
    assert merged["public_decision_maker_evidence_accepted"] == 2
    assert merged["decision_reconciliation"]["review_required"] is False

    class Validator:
        def validate(self, email):
            return SimpleNamespace(
                email=email,
                is_valid=True,
                confidence=0.75,
                is_role_address=False,
                is_disposable=False,
                has_mx=True,
                smtp_accepts=False,
            )

    plan = verify_contact_plan(merged, validator=Validator())
    assert plan["review_ready"] is False
    assert plan["outreach_ready"] is False
    assert plan["preferred_email"] is None


def test_single_directory_role_claim_cannot_create_decision_maker():
    from empire_os.buyer_discovery import (
        merge_public_decision_maker_evidence,
    )

    merged = merge_public_decision_maker_evidence(
        {"decision_maker": None, "contact_candidates": []},
        [{
            "name": "Terry Paris",
            "title": "Owner",
            "source_url": "https://www.bbb.org/example/all-star-roofing",
            "source_kind": "public_business_directory",
            "business_identity_correlated": True,
        }],
    )
    assert merged.get("decision_maker") is None
    assert merged["public_decision_maker_evidence_accepted"] == 0


def test_official_site_role_evidence_can_stand_alone():
    from empire_os.buyer_discovery import (
        merge_public_decision_maker_evidence,
    )

    merged = merge_public_decision_maker_evidence(
        {"decision_maker": None, "contact_candidates": []},
        [{
            "name": "Jane Smith",
            "title": "Founder",
            "source_url": "https://acme.example/about",
            "source_kind": "official_site",
        }],
    )
    assert merged["decision_maker"]["name"] == "Jane Smith"
    assert merged["public_decision_maker_evidence_accepted"] == 1


def test_conflicting_corroborated_public_people_fail_closed():
    from empire_os.buyer_discovery import (
        merge_public_decision_maker_evidence,
    )

    merged = merge_public_decision_maker_evidence(
        {"decision_maker": None, "contact_candidates": []},
        [
            {
                "name": "Jane Smith",
                "title": "Owner",
                "source_url": "https://one.example/jane",
                "source_kind": "public_business_directory",
            "business_identity_correlated": True,
            },
            {
                "name": "Jane Smith",
                "title": "Owner",
                "source_url": "https://two.example/jane",
                "source_kind": "professional_profile",
                "business_identity_correlated": True,
            },
            {
                "name": "John Smith",
                "title": "Owner",
                "source_url": "https://three.example/john",
                "source_kind": "public_business_directory",
            "business_identity_correlated": True,
            },
            {
                "name": "John Smith",
                "title": "Owner",
                "source_url": "https://four.example/john",
                "source_kind": "professional_profile",
                "business_identity_correlated": True,
            },
        ],
    )
    assert merged.get("decision_maker") is None
    assert (
        merged["decision_reconciliation"]["status"]
        == "ambiguous_public_identity"
    )
    assert merged["decision_reconciliation"]["review_required"] is True
    assert merged["public_decision_maker_evidence_accepted"] == 0


def test_public_decision_maker_does_not_override_conflicting_existing_person():
    from empire_os.buyer_discovery import (
        merge_public_decision_maker_evidence,
    )

    merged = merge_public_decision_maker_evidence(
        {
            "decision_maker": {
                "name": "Existing Person",
                "title": "Owner",
                "decision_score": 1.0,
            },
            "contact_candidates": [],
        },
        [
            {
                "name": "Jane Smith",
                "title": "Owner",
                "source_url": "https://one.example/jane",
                "source_kind": "public_business_directory",
            "business_identity_correlated": True,
            },
            {
                "name": "Jane Smith",
                "title": "Owner",
                "source_url": "https://two.example/jane",
                "source_kind": "professional_profile",
                "business_identity_correlated": True,
            },
        ],
    )
    assert merged["decision_maker"]["name"] == "Existing Person"
    assert merged["decision_reconciliation"]["status"] == "identity_conflict"
    assert merged["decision_reconciliation"]["review_required"] is True
    assert merged["public_decision_maker_evidence_accepted"] == 0



def _readiness_candidate():
    return build_candidate({
        "id": "11111111-1111-4111-8111-111111111111",
        "entity_id": "22222222-2222-4222-8222-222222222222",
        "business_name": "All Star Roofing",
        "niche": "roofing",
        "metro": "Austin, TX",
        "website": "https://allstarroofingtexas.com",
        "phone": "+1-512-477-7827",
        "buy_signal_score": 80,
    }, entity_id="22222222-2222-4222-8222-222222222222",
       entity_linked=True)


def _activated_buyer_row(**overrides):
    row = {
        "id": "33333333-3333-4333-8333-333333333333",
        "buyer_name": "All Star Roofing",
        "niche": "roofing",
        "metro": "Austin, TX",
        "is_active": True,
        "status": "active",
        "commercial_activation_state": "activated",
        "reviewed_at": "2026-09-19T10:00:00Z",
        "commercial_activated_at": "2026-09-19T10:01:00Z",
        "commercial_terms_source": "manual_contract",
        "commercial_terms_reference": "contract:test",
        "commercial_terms_verified_at": "2026-09-19T10:01:00Z",
        "capacity_verified_at": "2026-09-19T10:01:00Z",
        "delivery_verified_at": "2026-09-19T10:01:00Z",
        "destination_phone": "+15124777827",
        "webhook_url": None,
        "daily_cap": 10,
    }
    row.update(overrides)
    return row


def test_buyer_readiness_dossier_exposes_real_all_star_blockers():
    dossier = build_buyer_readiness_dossier(
        _readiness_candidate(),
        {
            "decision_maker": {
                "name": "Terry Paris",
                "title": "Owner",
                "decision_role": "economic_buyer",
                "decision_score": 1.0,
                "source": "public_web_corroborated",
            },
            "decision_reconciliation": {
                "status": "public_corroborated",
                "review_required": False,
            },
            "review_ready": False,
            "outreach_ready": False,
            "preferred_email": None,
        },
    )
    assert dossier["decision_maker_ready"] is True
    assert dossier["review_ready"] is False
    assert dossier["outreach_ready"] is False
    assert dossier["buyer_record_present"] is False
    assert dossier["buyer_activation_ready"] is False
    assert dossier["allocation_ready"] is False
    assert dossier["blockers"] == [
        "verified_person_bound_contact_missing",
        "buyer_record_missing",
    ]
    assert dossier["next_required"] == (
        "verified_person_bound_contact_missing"
    )
    assert dossier["write_authorized"] is False


def test_buyer_readiness_dossier_reuses_commercial_activation_gate():
    dossier = build_buyer_readiness_dossier(
        _readiness_candidate(),
        {
            "decision_maker": {
                "name": "Terry Paris",
                "title": "Owner",
                "decision_score": 1.0,
            },
            "decision_reconciliation": {
                "review_required": False,
            },
            "review_ready": True,
            "outreach_ready": True,
            "preferred_email": "terry@example.test",
        },
        buyer_row=_activated_buyer_row(
            commercial_activation_state="discovered",
        ),
    )
    assert dossier["buyer_record_present"] is True
    assert dossier["buyer_activation_ready"] is False
    assert dossier["buyer_activation_reason"] == (
        "buyer_not_commercially_activated"
    )
    assert dossier["blockers"] == [
        "buyer_not_commercially_activated"
    ]


def test_buyer_readiness_dossier_is_allocation_ready_only_after_activation():
    dossier = build_buyer_readiness_dossier(
        _readiness_candidate(),
        {
            "decision_maker": {
                "name": "Terry Paris",
                "title": "Owner",
                "decision_score": 1.0,
            },
            "decision_reconciliation": {
                "review_required": False,
            },
            "review_ready": True,
            "outreach_ready": True,
            "preferred_email": "terry@example.test",
        },
        buyer_row=_activated_buyer_row(),
    )
    assert dossier["blockers"] == []
    assert dossier["next_required"] is None
    assert dossier["buyer_activation_ready"] is True
    assert dossier["allocation_ready"] is True


def test_prior_smtp_verified_generated_contact_survives_lightweight_recheck():
    from types import SimpleNamespace
    from empire_os.buyer_discovery import (
        merge_generated_contact_evidence,
        verify_contact_plan,
    )

    enriched = {
        "decision_maker": {
            "name": "Jane Smith",
            "title": "CEO",
            "decision_score": 1.0,
        },
        "contact_candidates": [],
    }
    merged = merge_generated_contact_evidence(
        enriched,
        [{
            "email": "jane.smith@acme.test",
            "verification_state": "smtp_valid",
            "smtp_accepts": True,
            "has_mx": True,
            "confidence": 0.95,
        }],
    )

    class LightweightValidator:
        def validate(self, email):
            return SimpleNamespace(
                email=email,
                is_valid=True,
                confidence=0.75,
                is_role_address=False,
                is_disposable=False,
                has_mx=True,
                smtp_accepts=False,
            )

    plan = verify_contact_plan(
        merged,
        validator=LightweightValidator(),
    )

    assert plan["outreach_ready"] is True
    assert plan["verified_contacts"][0]["smtp_accepts"] is True
    assert plan["preferred_email"] == "jane.smith@acme.test"


def test_placeholder_referral_program_is_not_a_person_name():
    from empire_os.buyer_discovery import looks_like_person_name

    assert looks_like_person_name("Your Referral Program") is False
    assert looks_like_person_name("Kathy Thomas") is True


def test_company_routed_contact_requires_explicit_opt_in_and_economic_buyer():
    from types import SimpleNamespace
    from empire_os.buyer_discovery import verify_contact_plan

    class Validator:
        def validate(self, email):
            return SimpleNamespace(
                email=email,
                is_valid=False,
                confidence=0.0,
                is_role_address=True,
                is_disposable=False,
                has_mx=False,
                smtp_accepts=False,
            )

    enriched = {
        "decision_maker": {
            "name": "Peter Read",
            "title": "Managing Director",
            "decision_role": "economic_buyer",
            "decision_score": 1.0,
        },
        "decision_reconciliation": {"review_required": False},
        "site_evidence": {
            "domain_match": True,
            "domain": "2020solarpv.com",
            "expected_domain": "2020solarpv.com",
        },
        "contact_candidates": [{
            "email": "enquiries@2020solarpv.com",
            "source": "site_observed",
            "bound_to_decision_maker": False,
        }],
    }

    default = verify_contact_plan(
        enriched,
        validator=Validator(),
    )
    assert default["review_ready"] is False
    assert default["outreach_ready"] is False
    assert default["preferred_email"] is None

    routed = verify_contact_plan(
        enriched,
        validator=Validator(),
        allow_company_routed=True,
    )
    assert routed["review_ready"] is True
    assert routed["outreach_ready"] is True
    assert routed["preferred_email"] == "enquiries@2020solarpv.com"
    assert routed["contact_route"] == "company_routed"
    assert routed["person_bound"] is False
    assert routed["routing_name"] == "Peter Read"
    assert routed["routing_title"] == "Managing Director"

    weak = {
        **enriched,
        "decision_maker": {
            "name": "Pat Manager",
            "title": "Marketing Manager",
            "decision_role": "influencer",
            "decision_score": 0.5,
        },
    }
    blocked = verify_contact_plan(
        weak,
        validator=Validator(),
        allow_company_routed=True,
    )
    assert blocked["review_ready"] is False
    assert blocked["contact_route"] is None


def test_company_routed_aliases_include_enquiries_and_office():
    from empire_os.buyer_discovery import _is_company_routing_email

    assert _is_company_routing_email("enquiries@2020solarpv.com") is True
    assert _is_company_routing_email("info@3asconsultants.com") is True
    assert _is_company_routing_email("office@example.co.uk") is True
    assert _is_company_routing_email("peter@2020solarpv.com") is False


def test_solar_candidate_uses_solar_opportunity_map_offer():
    candidate = build_candidate({
        "id": "00000000-0000-0000-0000-000000000991",
        "business_name": "Example Solar Ltd",
        "niche": "solar",
        "metro": "United Kingdom",
        "website": "https://solar.example",
        "buy_signal_score": 95,
        "contact_name": "Jane Smith",
        "contact_title": "Managing Director",
    })

    assert candidate.offer_key == "solar_opportunity_map"
