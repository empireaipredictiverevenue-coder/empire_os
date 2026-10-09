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


def test_bounded_sitemap_profile_reaches_exact_person_contact_evidence(monkeypatch):
    from types import SimpleNamespace
    import empire_os.search_fabric.site_probe as sp
    root = "https://acme.test/"
    requests = []
    def doc(url, text, *, fmt="html", emails=()):
        return SimpleNamespace(
            url=url, canonical_url=url, text=text, format=fmt,
            title="Acme", description="", emails=list(emails),
            phones=[], socials=[], structured_data=[],
        )
    pages = {
        root: doc(root, "<h1>Acme</h1>"),
        root + "sitemap.xml": doc(
            root + "sitemap.xml",
            "<urlset><url><loc>https://acme.test/leadership/jane-smith/</loc></url></urlset>",
            fmt="xml",
        ),
        root + "leadership/jane-smith/": doc(
            root + "leadership/jane-smith/",
            "<h2>Jane Smith</h2><p>Chief Executive Officer</p>",
            emails=["jane@acme.test"],
        ),
    }
    def fetch(_session, url, **kwargs):
        requests.append(url)
        return pages.get(url)
    monkeypatch.setattr(sp, "_fetch", fetch)
    monkeypatch.setattr(sp.time, "sleep", lambda _duration: None)
    result = collect_public_person_contact_evidence(
        business_name="Acme",
        website=root,
        person_name="Jane Smith",
        person_title="Chief Executive Officer",
        probe_fn=sp.probe_site,
        search_fn=lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("Search engine unnecessary when sitemap yields proof")
        ),
        max_queries=2,
        max_pages_total=3,
    )
    assert result["evidence"] == [{
        "name": "Jane Smith",
        "title": "Chief Executive Officer",
        "email": "jane@acme.test",
        "source_url": root + "leadership/jane-smith/",
        "source_kind": "official_site",
        "role_corroborated": True,
        "direct_publication": True,
        "business_identity_correlated": True,
        "decision_role": result["decision_role"],
        "decision_score": result["decision_score"],
    }]
    assert requests == [root, root + "sitemap.xml", root + "leadership/jane-smith/"]
    assert result["outbound_authorized"] is False
    assert result["database_write_performed"] is False


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
    assert calls == ["https://acme.example"]
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
