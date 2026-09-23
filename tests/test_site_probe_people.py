from empire_os.search_fabric.site_probe import _schema_evidence, _sitemap_people_candidates, _visible_people_from_html


def test_schema_people_are_separate_from_business_names():
    records = [{
        "@type": "Organization",
        "name": "Acme Ltd",
        "employee": [{
            "@type": "Person",
            "name": "Jane Smith",
            "jobTitle": "Managing Director",
            "email": "mailto:jane@acme.test",
            "url": "https://acme.test/team/jane",
        }],
    }]
    evidence = _schema_evidence(records)
    assert evidence["business_names"] == ["Acme Ltd"]
    assert evidence["people"] == [{
        "name": "Jane Smith",
        "title": "Managing Director",
        "email": "jane@acme.test",
        "url": "https://acme.test/team/jane",
    }]


def test_schema_people_are_deduplicated_by_evidence_tuple():
    person = {"@type":"Person","name":"Alex Doe","jobTitle":"Founder","email":"alex@x.test"}
    evidence = _schema_evidence([person, person.copy()])
    assert len(evidence["people"]) == 1
    assert evidence["business_names"] == []


def test_fetch_forwards_bounded_timeout(monkeypatch):
    import empire_os.search_fabric.site_probe as sp
    seen = {}
    class Response:
        status_code = 200
        headers = {"Content-Type":"text/html"}
        content = b"<html></html>"
        url = "https://acme.test/"
        encoding = "utf-8"
    class Session:
        def get(self, url, timeout, allow_redirects):
            seen["timeout"] = timeout
            return Response()
    monkeypatch.setattr(sp, "decode_document", lambda **kwargs: type("Doc",(),{
        "url":kwargs["url"],"canonical_url":kwargs["url"],"format":"html","text":"",
        "title":"Acme","description":"","structured_data":[],"emails":[],"phones":[],"socials":[]
    })())
    assert sp._fetch(Session(), "https://acme.test", timeout=3.5) is not None
    assert seen["timeout"] == 3.5


def test_probe_stops_internal_fetches_when_budget_exhausted(monkeypatch):
    import empire_os.search_fabric.site_probe as sp
    calls = []
    doc = type("Doc",(),{
        "url":"https://acme.test/","canonical_url":"https://acme.test/","format":"html",
        "text":'<a href="/contact">Contact</a><a href="/team">Team</a>',
        "title":"Acme","description":"","structured_data":[],"emails":[],"phones":[],"socials":[]
    })()
    def fake_fetch(session, url, *, timeout=15.0, public_only=False):
        calls.append(url)
        return doc
    times = iter([0.0, 2.0, 2.0, 2.0, 2.0])
    monkeypatch.setattr(sp, "_fetch", fake_fetch)
    monkeypatch.setattr(sp.time, "monotonic", lambda: next(times, 2.0))
    monkeypatch.setattr(sp.time, "sleep", lambda _: None)
    result = sp.probe_site("https://acme.test", max_pages=4, request_timeout=1, time_budget_seconds=1)
    assert len(calls) == 1
    assert result["budget_exhausted"] is True


def test_probe_preserves_bounded_page_email_context(monkeypatch):
    import empire_os.search_fabric.site_probe as sp

    doc = type("Doc", (), {
        "url": "https://acme.test/team",
        "canonical_url": "https://acme.test/team",
        "format": "html",
        "text": (
            "<html><body>Jane Smith Chief Executive Officer "
            "jane@acme.test</body></html>"
        ),
        "title": "Meet the Team",
        "description": "",
        "structured_data": [],
        "emails": ["jane@acme.test"],
        "phones": [],
        "socials": [],
    })()

    monkeypatch.setattr(
        sp,
        "_fetch",
        lambda session, url, *, timeout=15.0, public_only=False: doc,
    )
    result = sp.probe_site(
        "https://acme.test/team",
        max_pages=1,
        request_timeout=1,
        time_budget_seconds=1,
    )

    page = result["pages_checked"][0]
    assert page["emails"] == ["jane@acme.test"]
    assert "Jane Smith Chief Executive Officer" in page["visible_text"]
    assert len(page["visible_text"]) <= 12_000


def test_people_priority_visits_team_before_locations():
    import empire_os.search_fabric.site_probe as sp

    html = """
    <a href="/locations/austin/">Austin Location</a>
    <a href="/contact/">Contact</a>
    <a href="/about-us/">About Us</a>
    <a href="/about-us/meet-the-team/">Meet the Team</a>
    """
    urls = sp._internal_candidates(
        html,
        "https://acme.test/",
        priority="people",
    )

    assert urls[0] == "https://acme.test/about-us/meet-the-team/"
    assert urls[1] == "https://acme.test/about-us/"
    assert urls[2] == "https://acme.test/contact/"


def test_people_priority_adds_common_first_party_paths():
    import empire_os.search_fabric.site_probe as sp

    urls = sp._common_candidates(
        "https://acme.test/",
        priority="people",
    )

    assert urls[:4] == [
        "https://acme.test/about-us/meet-the-team/",
        "https://acme.test/meet-the-team/",
        "https://acme.test/our-team/",
        "https://acme.test/team/",
    ]
    assert sp._common_candidates(
        "https://acme.test/",
        priority="default",
    ) == []


def test_people_priority_follows_profile_link_from_team_page(monkeypatch):
    import empire_os.search_fabric.site_probe as sp

    docs = {
        "https://acme.test/": type("Doc", (), {
            "url": "https://acme.test/",
            "canonical_url": "https://acme.test/",
            "format": "html",
            "text": '<a href="/team/">Team</a>',
            "title": "Acme",
            "description": "",
            "structured_data": [],
            "emails": [],
            "phones": [],
            "socials": [],
        })(),
        "https://acme.test/team/": type("Doc", (), {
            "url": "https://acme.test/team/",
            "canonical_url": "https://acme.test/team/",
            "format": "html",
            "text": '<a href="/team/jane-smith/">Jane Smith, CEO</a>',
            "title": "Team",
            "description": "",
            "structured_data": [],
            "emails": [],
            "phones": [],
            "socials": [],
        })(),
        "https://acme.test/team/jane-smith/": type("Doc", (), {
            "url": "https://acme.test/team/jane-smith/",
            "canonical_url": "https://acme.test/team/jane-smith/",
            "format": "html",
            "text": "Jane Smith CEO jane@acme.test",
            "title": "Jane Smith",
            "description": "",
            "structured_data": [],
            "emails": ["jane@acme.test"],
            "phones": [],
            "socials": [],
        })(),
    }

    def fake_fetch(session, url, *, timeout=15.0, public_only=False):
        return docs.get(url)

    monkeypatch.setattr(sp, "_fetch", fake_fetch)
    monkeypatch.setattr(sp.time, "sleep", lambda _: None)
    result = sp.probe_site(
        "https://acme.test/",
        max_pages=4,
        request_timeout=1,
        time_budget_seconds=4,
        page_priority="people",
    )

    urls = [row["url"] for row in result["pages_checked"]]
    assert "https://acme.test/team/jane-smith/" in urls
    assert "jane@acme.test" in result["emails"]

def test_visible_people_recovers_named_ceo_without_schema():
    import empire_os.search_fabric.site_probe as sp

    people = sp._visible_people_from_html(
        "<div><h2>Jane Smith</h2><p>Founder & CEO</p>"
        "<a href='mailto:jane@acme.test'>Email</a></div>",
        page_url="https://acme.test/team/jane",
        page_title="Jane Smith",
        emails=["jane@acme.test"],
    )

    assert people
    assert people[0]["name"] == "Jane Smith"
    assert people[0]["title"].lower() in {"founder", "ceo"}
    assert people[0]["email"] == "jane@acme.test"


def test_visible_people_rejects_generic_team_heading():
    import empire_os.search_fabric.site_probe as sp

    people = sp._visible_people_from_html(
        "<div><h2>Meet The Team</h2><p>CEO</p></div>",
        page_url="https://acme.test/team",
        page_title="Meet The Team",
        emails=[],
    )

    assert people == []

def test_visible_people_pairs_adjacent_team_card_blocks():
    import empire_os.search_fabric.site_probe as sp

    people = sp._visible_people_from_html(
        "<section><h3>John Carter</h3><p>Owner & President</p></section>",
        page_url="https://acme.test/our-team/",
        page_title="Our Team",
        emails=["john@acme.test"],
    )

    assert people
    assert people[0]["name"] == "John Carter"
    assert people[0]["email"] == "john@acme.test"


def test_visible_people_extracts_founded_by_phrase():
    html = """
    <html><body>
      <p>Founded by Jane Smith in 2012, the company serves Houston.</p>
    </body></html>
    """
    people = _visible_people_from_html(
        html,
        page_url="https://example.com/about",
    )
    assert any(
        p["name"] == "Jane Smith" and p["title"].lower() == "owner"
        for p in people
    )


def test_visible_people_extracts_role_name_phrase():
    html = """
    <html><body>
      <p>Our President Michael Carter leads the roofing team.</p>
    </body></html>
    """
    people = _visible_people_from_html(
        html,
        page_url="https://example.com/about",
    )
    assert any(
        p["name"] == "Michael Carter"
        and p["title"].lower() == "president"
        for p in people
    )


def test_sitemap_people_candidates_find_hidden_team_pages(monkeypatch):
    import time
    import empire_os.search_fabric.site_probe as sp

    class Doc:
        def __init__(self, text):
            self.text = text

    def fake_fetch(session, url, timeout, public_only=False):
        if url.endswith("/sitemap.xml"):
            return Doc(
                "<urlset>"
                "<url><loc>https://acme.test/services</loc></url>"
                "<url><loc>https://acme.test/about/leadership</loc></url>"
                "</urlset>"
            )
        return None

    monkeypatch.setattr(sp, "_fetch", fake_fetch)
    rows = _sitemap_people_candidates(
        object(),
        "https://acme.test/",
        timeout=2.0,
        deadline=time.monotonic() + 5,
    )
    assert rows == ["https://acme.test/about/leadership"]
