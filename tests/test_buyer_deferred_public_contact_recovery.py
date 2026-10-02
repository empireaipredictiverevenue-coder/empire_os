from types import SimpleNamespace

import scripts.run_buyer_deferred_enrichment as worker


def _candidate(source="website_structured_data"):
    return SimpleNamespace(
        business_name="Elite Air Conditioning and Plumbing",
        website="https://eliteaustinac.com/",
        contact_name="Chris Shaffer",
        contact_title="Co-Founder",
        contact_source=source,
    )


def test_trusted_persisted_identity_uses_direct_contact_recovery(monkeypatch):
    calls = []
    monkeypatch.setattr(
        worker,
        "collect_public_person_contact_evidence",
        lambda **kwargs: (
            calls.append(kwargs)
            or {
                "attempted": True,
                "evidence": [{
                    "name": "Chris Shaffer",
                    "title": "Co-Founder",
                    "email": "chris@eliteaustinac.com",
                    "source_url": "https://eliteaustinac.com/about-us/",
                    "source_kind": "official_site",
                    "role_corroborated": True,
                    "direct_publication": True,
                }],
            }
        ),
    )
    monkeypatch.setattr(
        worker,
        "verify_contact_plan",
        lambda enriched, *, validator, allow_company_routed: {
            "decision_maker": enriched["decision_maker"],
            "verified_contacts": enriched["contact_candidates"],
            "preferred_email": "chris@eliteaustinac.com",
            "contact_route": "person_bound",
            "person_bound": True,
            "review_ready": True,
            "outreach_ready": True,
        },
    )

    result = worker._direct_public_contact_recovery(
        _candidate(),
        {
            "review_ready": False,
            "contacts": [],
            "decision_maker": None,
        },
    )

    assert len(calls) == 1
    assert calls[0]["max_queries"] == 2
    assert calls[0]["max_results_per_query"] == 4
    assert calls[0]["max_pages_total"] == 3
    assert result["review_ready"] is True
    assert result["outreach_ready"] is True
    assert result["person_bound"] is True
    assert result["preferred_email"] == "chris@eliteaustinac.com"


def test_untrusted_persisted_identity_cannot_search(monkeypatch):
    monkeypatch.setattr(
        worker,
        "collect_public_person_contact_evidence",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("untrusted identity must not search")
        ),
    )
    original = {
        "review_ready": False,
        "contacts": [],
        "decision_maker": None,
    }
    result = worker._direct_public_contact_recovery(
        _candidate(source="canonical_prospect"),
        original,
    )
    assert result == original


def test_main_hot_loop_disables_public_search_before_direct_recovery():
    text = open(
        "scripts/run_buyer_deferred_enrichment.py",
        encoding="utf-8",
    ).read()
    start = text.index("if result is None:")
    end = text.index("identity_recovered = False", start)
    hot = text[start:end]
    assert '"allow_public_person_contact_search": True' not in hot
    assert hot.count('"allow_public_person_contact_search": False') >= 2
