import importlib

search_module = importlib.import_module("empire_os.search_fabric.search")


def test_auto_search_uses_existing_recovery_engine(monkeypatch):
    monkeypatch.setattr(search_module, "BRAVE_API_KEY", "")
    monkeypatch.setattr(search_module, "_get_cache", lambda *args: None)
    monkeypatch.setattr(search_module, "_set_cache", lambda *args: None)

    calls = []

    def fake_fetch(engine, query, num):
        calls.append(engine["name"])
        if engine["name"] != "bing_rss":
            return None
        return """
        <rss><channel>
          <item>
            <title>Best Denver Roofing Companies</title>
            <link>https://comparison.example/denver-roofing</link>
            <description>
              Compare Denver roofing companies and contractors.
            </description>
          </item>
        </channel></rss>
        """

    monkeypatch.setattr(search_module, "_fetch", fake_fetch)

    result = search_module.search("Denver roofing", num=5)

    assert result["organic"]
    assert result["searchParameters"]["engine"] == "bing_rss"
    assert result["searchParameters"]["quality_gate"] == "lexical_v1"
    assert "bing_html" in calls
    assert "duckduckgo_html" in calls
    assert "bing_rss" in calls


def test_explicit_engine_does_not_expand_to_recovery_chain(monkeypatch):
    monkeypatch.setattr(search_module, "_get_cache", lambda *args: None)
    monkeypatch.setattr(search_module, "_set_cache", lambda *args: None)

    calls = []

    def fake_fetch(engine, query, num):
        calls.append(engine["name"])
        return None

    monkeypatch.setattr(search_module, "_fetch", fake_fetch)

    result = search_module.search(
        "Denver roofing",
        num=5,
        engine="bing_html",
    )

    assert result["organic"] == []
    assert calls == ["bing_html"]



def test_rejection_diagnostic_writes_to_stderr(monkeypatch, capsys):
    monkeypatch.setattr(search_module, "_get_cache", lambda *args: None)
    monkeypatch.setattr(search_module, "_set_cache", lambda *args: None)
    monkeypatch.setattr(search_module, "_fetch", lambda *args: "raw")
    monkeypatch.setitem(
        search_module.PARSERS,
        "bing_html",
        lambda raw: [{
            "title": "Completely unrelated result",
            "link": "https://example.com/unrelated",
            "snippet": "Nothing about the requested market.",
            "position": 1,
        }],
    )

    result = search_module.search(
        "Denver roofing",
        num=5,
        engine="bing_html",
    )

    captured = capsys.readouterr()

    assert result["organic"] == []
    assert "bing_html rejected" in captured.err



def test_domain_query_does_not_match_on_com_token_only():
    result = {
        "title": "Brandon Sanderson White Sand",
        "link": "https://brandonsanderson.com/white-sand",
        "snippet": "Fantasy graphic novel.",
    }

    score = search_module._result_relevance(
        result,
        '"goldenspikeroofing.com"',
    )

    assert score == 0.0



def test_public_fetch_fails_fast_on_timeout(monkeypatch):
    monkeypatch.setattr(search_module, "_polite", lambda *args: None)
    monkeypatch.setattr(search_module, "_next_proxy", lambda: None)
    monkeypatch.setattr(search_module, "SEARCH_PUBLIC_TIMEOUT", 4.0)
    monkeypatch.setattr(search_module, "SEARCH_PUBLIC_ATTEMPTS", 1)

    calls = []

    def timeout_get(*args, **kwargs):
        calls.append(kwargs.get("timeout"))
        raise search_module.requests.exceptions.Timeout()

    monkeypatch.setattr(search_module.requests, "get", timeout_get)

    engine = next(
        row for row in search_module.ENGINES
        if row["name"] == "bing_html"
    )
    result = search_module._fetch(
        engine,
        "Denver roofing",
        5,
    )

    assert result is None
    assert calls == [4.0]



def test_engine_circuit_breaker_opens_after_repeated_failures(monkeypatch):
    monkeypatch.setattr(search_module, "SEARCH_ENGINE_FAILURE_THRESHOLD", 2)
    monkeypatch.setattr(search_module, "SEARCH_ENGINE_COOLDOWN_SECONDS", 300.0)
    monkeypatch.setattr(search_module, "_polite", lambda *args: None)
    monkeypatch.setattr(search_module, "_next_proxy", lambda: None)
    monkeypatch.setattr(search_module, "SEARCH_PUBLIC_ATTEMPTS", 1)

    search_module._engine_health.clear()

    class Response:
        status_code = 403

    calls = []

    def blocked_get(*args, **kwargs):
        calls.append(1)
        return Response()

    monkeypatch.setattr(search_module.requests, "get", blocked_get)

    engine = next(
        row for row in search_module.ENGINES
        if row["name"] == "mojeek"
    )

    assert search_module._fetch(engine, "roofing leads", 5) is None
    assert search_module._fetch(engine, "roofing calls", 5) is None
    assert search_module._fetch(engine, "roofing buyers", 5) is None

    assert len(calls) == 2
    assert search_module._engine_available("mojeek") is False


def test_search_domains_retries_without_exact_match_quotes(monkeypatch):
    calls = []

    def fake_search(query, num=20, engine=None):
        calls.append(query)
        if '"' in query:
            return {"organic": []}
        return {
            "organic": [
                {
                    "title": "Austin Roofing Leads",
                    "link": "https://buyer.example/roofing",
                    "snippet": "Roofing leads in Austin Texas.",
                }
            ]
        }

    monkeypatch.setattr(search_module, "search", fake_search)

    domains = search_module.search_domains(
        '"buy roofing leads" Austin TX',
        num=5,
    )

    assert domains == ["buyer.example"]
    assert calls == [
        '"buy roofing leads" Austin TX',
        "buy roofing leads Austin TX",
    ]


def test_broaden_query_only_removes_exact_match_quotes():
    assert search_module._broaden_query(
        '"buy roofing leads" Austin TX'
    ) == "buy roofing leads Austin TX"


def test_high_level_search_registry_has_redundant_keyless_recovery():
    from empire_os.search_fabric.engines import active_engines

    names = {engine.name for engine in active_engines()}

    assert "duckduckgo_html" in names
    assert "bing_rss" in names
    assert "duckduckgo_lite" in names
    assert "mojeek" in names
