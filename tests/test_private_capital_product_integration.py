from empire_os.private_capital_product_integration import build_private_capital_product_integration


def row(identity, kind, **fields):
    return {
        "id": identity,
        "tenant_id": "tenant-a",
        "backend": "empiredb",
        "evidence_class": "OBSERVED",
        "source_ref": "source:" + identity,
        "observed_at": "2026-10-02T12:00:00+00:00",
        "kind": kind,
        **fields,
    }


def test_private_capital_builds_evidence_graph_without_commercial_authority():
    evidence = [
        row("sponsor", "company", name="Sponsor Co"),
        row("target-co", "company", name="Target Co"),
        row("segment-1", "segment", domain="private_capital", name="HVAC"),
        row("member-1", "member", domain="private_capital", entity_id="target-co", segment_id="segment-1"),
        row("target-1", "target", domain="private_capital", sponsor_id="sponsor", company_id="target-co", segment_id="segment-1"),
        row("opp-1", "opportunity", domain="private_capital", company_id="target-co", statement="Observed acquisition thesis"),
        row("intent-1", "deal_intent", domain="private_capital", company_id="target-co", statement="Observed public intent"),
    ]

    result = build_private_capital_product_integration(evidence, tenant_id="tenant-a")

    assert result["opportunity_count"] == 1
    assert result["deal_intent_observed"] is True
    assert result["execution_authority"] == "none"
    assert result["enterprise_offer_readiness"]["binding_terms_ready"] is False
    assert result["paid_proof"]["state"] == "UNVERIFIED"
    assert result["actual_revenue"] is False
    assert result["unknown_stays_unknown"] is True


def test_private_capital_rejects_noncanonical_evidence():
    result = build_private_capital_product_integration(
        [row("bad", "company", name="Bad", backend="legacy")],
        tenant_id="tenant-a",
    )

    assert result["evidence_state"] == "UNKNOWN"
    assert result["rejections"]["noncanonical_backend"] == 1
    assert result["actual_revenue"] is False
