from empire_os.competitor_ecosystem_mining import (
    build_ecosystem_snapshot,
    discover_company_ecosystem,
)


def _homepage():
    return """
    <html><body>
      <a href="/projects">Recent Projects</a>
      <a href="/reviews">Customer Reviews</a>
      <a href="/partners">Manufacturer Partners</a>
    </body></html>
    """


def _fetch(url):
    if url == "https://roofer.example":
        return _homepage()
    if url == "https://roofer.example/projects":
        return "<html><body><h1>Projects</h1></body></html>"
    if url == "https://roofer.example/reviews":
        return "<html><body><h1>Reviews</h1></body></html>"
    if url == "https://roofer.example/partners":
        return """
        <html><body>
          <a href="https://manufacturer.example/contractors">Manufacturer</a>
          <a href="https://facebook.com/roofer">Facebook</a>
        </body></html>
        """
    return None


def test_company_ecosystem_discovers_first_party_surfaces():
    result = discover_company_ecosystem(
        entity_id="entity-1",
        company_name="Example Roofing",
        company_website="roofer.example",
        fetch_fn=_fetch,
    )

    assert result["homepage_observed"] is True
    assert result["case_study_surface_count"] == 1
    assert result["testimonial_surface_count"] == 1
    assert result["partner_surface_count"] == 1
    assert result["surface_count"] == 3


def test_partner_surface_yields_external_domain_candidate_only():
    result = discover_company_ecosystem(
        entity_id="entity-1",
        company_name="Example Roofing",
        company_website="https://roofer.example",
        fetch_fn=_fetch,
    )

    assert len(result["external_relationship_candidates"]) == 1
    rel = result["external_relationship_candidates"][0]
    assert rel["external_domain"] == "manufacturer.example"
    assert rel["category"] == "partner"
    assert rel["partner_status_inferred"] is False


def test_ecosystem_never_promotes_customer_or_partner_relationships():
    result = discover_company_ecosystem(
        entity_id="entity-1",
        company_name="Example Roofing",
        company_website="https://roofer.example",
        fetch_fn=_fetch,
    )

    assert result["customer_relationship_inferred"] is False
    assert result["partner_relationship_inferred"] is False
    assert result["buyer_intent_inferred"] is False
    assert result["commercial_intent_inferred"] is False


def test_snapshot_aggregates_company_surface_counts():
    result = build_ecosystem_snapshot(
        companies=[
            {
                "entity_id": "entity-1",
                "company_name": "Example Roofing",
                "company_domain": "roofer.example",
            },
            {
                "entity_id": "entity-2",
                "company_name": "No Site Roofing",
                "company_domain": "nosite.example",
            },
        ],
        fetch_fn=_fetch,
        max_workers=2,
    )

    assert result["company_count"] == 2
    assert result["homepage_observed_count"] == 1
    assert result["case_study_company_count"] == 1
    assert result["testimonial_company_count"] == 1
    assert result["partner_surface_company_count"] == 1
    assert result["external_relationship_candidate_count"] == 1
    assert result["buyer_intent_inferred"] is False
    assert result["commercial_intent_inferred"] is False
    assert result["outreach_enabled"] is False
    assert result["execution_authority"] == "none"
