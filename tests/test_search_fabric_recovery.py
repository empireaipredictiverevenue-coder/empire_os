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
