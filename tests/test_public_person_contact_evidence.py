from empire_os.public_person_contact_evidence import (
    collect_public_person_contact_evidence,
)


def _search_factory(url):
    def fake_search(query, num=6, engine=None, use_cache=True):
        return {
            "organic": [{
                "title": "Jane Smith",
                "link": url,
                "snippet": "Jane Smith CEO",
                "position": 1,
            }]
        }
    return fake_search


def test_exact_first_party_person_email_is_accepted():
    result = collect_public_person_contact_evidence(
        business_name="Acme Roofing",
        website="https://acme.example",
        person_name="Jane Smith",
        person_title="CEO",
        search_fn=_search_factory("https://acme.example/team/jane"),
        probe_fn=lambda *args, **kwargs: {
            "ok": True,
            "people": [{
                "name": "Jane Smith",
                "title": "CEO",
                "email": "jane@acme.example",
                "url": "https://acme.example/team/jane",
            }],
        },
    )
    assert result["attempted"] is True
    assert result["pages_inspected"] == 1
    assert result["evidence"][0]["email"] == "jane@acme.example"
    assert result["evidence"][0]["source_kind"] == "official_site"
    assert result["execution_authority"] == "none"
    assert result["outbound_authorized"] is False


def test_wrong_person_is_rejected():
    result = collect_public_person_contact_evidence(
        business_name="Acme Roofing",
        website="https://acme.example",
        person_name="Jane Smith",
        person_title="CEO",
        search_fn=_search_factory("https://acme.example/team"),
        probe_fn=lambda *args, **kwargs: {
            "ok": True,
            "people": [{
                "name": "John Smith",
                "title": "Founder",
                "email": "john@acme.example",
            }],
        },
    )
    assert result["evidence"] == []


def test_off_domain_email_is_rejected():
    result = collect_public_person_contact_evidence(
        business_name="Acme Roofing",
        website="https://acme.example",
        person_name="Jane Smith",
        person_title="CEO",
        search_fn=_search_factory("https://www.bbb.org/acme"),
        probe_fn=lambda *args, **kwargs: {
            "ok": True,
            "people": [{
                "name": "Jane Smith",
                "title": "CEO",
                "email": "jane@gmail.com",
            }],
        },
    )
    assert result["evidence"] == []


def test_unsupported_source_is_not_probed():
    calls = []

    def probe(*args, **kwargs):
        calls.append(args[0])
        return {"ok": True, "people": []}

    result = collect_public_person_contact_evidence(
        business_name="Acme Roofing",
        website="https://acme.example",
        person_name="Jane Smith",
        person_title="CEO",
        search_fn=_search_factory("https://random-social.example/jane"),
        probe_fn=probe,
    )
    assert calls == []
    assert result["evidence"] == []


def test_directory_exact_person_email_is_observation_only():
    result = collect_public_person_contact_evidence(
        business_name="Acme Roofing",
        website="https://acme.example",
        person_name="Jane Smith",
        person_title="CEO",
        search_fn=_search_factory("https://www.bbb.org/acme/jane"),
        probe_fn=lambda *args, **kwargs: {
            "ok": True,
            "people": [{
                "name": "Jane Smith",
                "title": "CEO",
                "email": "jane@acme.example",
                "url": "https://www.bbb.org/acme/jane",
            }],
        },
    )
    assert result["evidence"][0]["source_kind"] == "public_business_directory"
    assert result["outbound_authorized"] is False
    assert result["database_write_performed"] is False
