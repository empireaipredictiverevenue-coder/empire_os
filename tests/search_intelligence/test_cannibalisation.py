from empire_os.search_intelligence.cannibalisation import detect_cannibalisation


def test_detects_observed_overlap_without_executing():
    findings = detect_cannibalisation([
        {
            "url": "https://example.com/a",
            "target_query": "roof repair london",
            "search_intent": "commercial",
            "topic": "roof repair",
            "content_quality_score": 0.9,
        },
        {
            "url": "https://example.com/b",
            "target_query": "roof repair london",
            "search_intent": "commercial",
            "topic": "roof repair",
            "content_quality_score": 0.7,
        },
    ])
    assert len(findings) == 1
    assert findings[0].execution_allowed is False
    assert findings[0].evidence["candidate_primary_url"] == "https://example.com/a"


def test_no_overlap_evidence_means_no_finding():
    assert detect_cannibalisation([
        {"url": "https://example.com/a", "topic": "roofing"},
        {"url": "https://example.com/b", "topic": "solar"},
    ]) == []
