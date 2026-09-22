from empire_os.search_fabric import search as search_module


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
