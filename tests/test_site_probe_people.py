from empire_os.search_fabric.site_probe import _schema_evidence


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
    def fake_fetch(session, url, *, timeout=15.0):
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
        lambda session, url, *, timeout=15.0: doc,
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
