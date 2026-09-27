from empire_os.search_intelligence.internal_links import analyze_internal_links


def test_internal_link_findings_are_evidence_based():
    pages = [
        {"url": "https://example.com/a", "topic": "roofing"},
        {"url": "https://example.com/b", "topic": "roofing"},
        {"url": "https://example.com/c", "topic": "solar"},
    ]
    links = [
        {"source_url": "https://example.com/a", "target_url": "https://example.com/b", "anchor_text": "roofing"},
        {"source_url": "https://example.com/a", "target_url": "https://example.com/missing", "anchor_text": "missing"},
    ]
    findings = analyze_internal_links(
        pages,
        links,
        excessive_outgoing_threshold=1,
        weak_cluster_min_related_links=1,
    )
    kinds = {(f.kind, f.page_url) for f in findings}
    assert ("broken_internal_target", "https://example.com/a") in kinds
    assert ("excessive_internal_links", "https://example.com/a") in kinds
    assert ("orphan_page", "https://example.com/c") in kinds
    assert ("weak_topic_cluster", "https://example.com/c") in kinds


def test_anchor_concentration_requires_observed_links():
    pages = [
        {"url": "https://example.com/a"},
        {"url": "https://example.com/b"},
    ]
    links = [
        {"source_url": "https://example.com/a", "target_url": "https://example.com/b", "anchor_text": "same"}
        for _ in range(5)
    ]
    findings = analyze_internal_links(pages, links)
    match = [f for f in findings if f.kind == "anchor_over_concentration"]
    assert len(match) == 1
    assert match[0].evidence["ratio"] == 1.0
