from empire_os.competitor_audience_sweep import (
    _is_public_http_url,
    discover_competitor_audience_evidence,
)


def _search_result(url="https://comparison.example/denver-roofers"):
    return {
        "organic": [{
            "title": "Best Denver Roofing Companies",
            "link": url,
            "snippet": "Compare top Denver roofing companies and reviews.",
            "position": 1,
        }]
    }


def _comparison_html():
    return """
    <html>
      <body>
        <h1>Best Denver Roofing Companies</h1>
        <p>Elite Roofing & Solar</p>
        <p>Golden Spike Roofing Inc</p>
        <a href="https://eliteroofingandsolar.com/">Elite</a>
        <a href="https://goldenspikeroofing.com/">Golden Spike</a>
      </body>
    </html>
    """


def _candidate():
    return {
        "entity_id": "1ae59b78-4ec7-5923-b3db-9a864f2ba0d8",
        "company_name": "Golden Spike Roofing Inc",
        "company_domain": "goldenspikeroofing.com",
    }


def test_public_url_filter_blocks_private_targets():
    assert _is_public_http_url("https://example.com/path") is True
    assert _is_public_http_url("http://127.0.0.1/admin") is False
    assert _is_public_http_url("http://10.0.0.5/") is False
    assert _is_public_http_url("http://localhost:8080/") is False
    assert _is_public_http_url("file:///etc/passwd") is False


def test_discovery_requires_same_public_page_evidence():
    calls = []

    def search_fn(query, num=10):
        calls.append((query, num))
        return _search_result()

    def fetch_fn(url):
        assert url == "https://comparison.example/denver-roofers"
        return _comparison_html()

    evidence = discover_competitor_audience_evidence(
        competitor_key="elite-roofing-solar",
        competitor_name="Elite Roofing & Solar",
        competitor_domain="eliteroofingandsolar.com",
        market_query="Denver roofing",
        candidates=[_candidate()],
        search_fn=search_fn,
        fetch_fn=fetch_fn,
        observed_at="2026-09-22T10:18:02+00:00",
    )

    assert calls
    assert len(evidence) == 1

    row = evidence[0]
    assert row["entity_id"] == _candidate()["entity_id"]
    assert row["company_name"] == "Golden Spike Roofing Inc"
    assert row["competitor_key"] == "elite-roofing-solar"
    assert row["evidence_type"] == "comparison_mention"
    assert row["source_ref"] == (
        "https://comparison.example/denver-roofers"
    )
    assert row["confidence"] == 0.90


def test_search_snippet_alone_does_not_create_relationship_evidence():
    def search_fn(query, num=10):
        return _search_result()

    def fetch_fn(url):
        return """
        <html><body>
          <h1>Best Denver Roofing Companies</h1>
          <p>Unrelated roofing directory page.</p>
        </body></html>
        """

    evidence = discover_competitor_audience_evidence(
        competitor_key="elite-roofing-solar",
        competitor_name="Elite Roofing & Solar",
        competitor_domain="eliteroofingandsolar.com",
        market_query="Denver roofing",
        candidates=[_candidate()],
        search_fn=search_fn,
        fetch_fn=fetch_fn,
        observed_at="2026-09-22T10:18:02+00:00",
    )

    assert evidence == []


def test_candidate_mention_without_competitor_is_rejected():
    def search_fn(query, num=10):
        return _search_result()

    def fetch_fn(url):
        return """
        <html><body>
          <h1>Best Denver Roofing Companies</h1>
          <p>Golden Spike Roofing Inc</p>
          <a href="https://goldenspikeroofing.com/">Golden Spike</a>
        </body></html>
        """

    evidence = discover_competitor_audience_evidence(
        competitor_key="elite-roofing-solar",
        competitor_name="Elite Roofing & Solar",
        competitor_domain="eliteroofingandsolar.com",
        market_query="Denver roofing",
        candidates=[_candidate()],
        search_fn=search_fn,
        fetch_fn=fetch_fn,
        observed_at="2026-09-22T10:18:02+00:00",
    )

    assert evidence == []


def test_discovery_deduplicates_same_company_source_page_across_queries():
    def search_fn(query, num=10):
        return _search_result()

    evidence = discover_competitor_audience_evidence(
        competitor_key="elite-roofing-solar",
        competitor_name="Elite Roofing & Solar",
        competitor_domain="eliteroofingandsolar.com",
        market_query="Denver roofing",
        candidates=[_candidate()],
        search_fn=search_fn,
        fetch_fn=lambda url: _comparison_html(),
        observed_at="2026-09-22T10:18:02+00:00",
    )

    assert len(evidence) == 1


def test_discovery_never_emits_buyer_or_commercial_intent():
    def search_fn(query, num=10):
        return _search_result()

    evidence = discover_competitor_audience_evidence(
        competitor_key="elite-roofing-solar",
        competitor_name="Elite Roofing & Solar",
        competitor_domain="eliteroofingandsolar.com",
        market_query="Denver roofing",
        candidates=[_candidate()],
        search_fn=search_fn,
        fetch_fn=lambda url: _comparison_html(),
        observed_at="2026-09-22T10:18:02+00:00",
    )

    row = evidence[0]
    assert "buyer_intent" not in row
    assert "commercial_intent" not in row
    assert "outreach_enabled" not in row
