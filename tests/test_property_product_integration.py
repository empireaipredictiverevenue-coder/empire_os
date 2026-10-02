from empire_os.property_product_integration import build_property_product_integration


def observation(**overrides):
    row = {
        "tenant_id": "tenant-a",
        "property_id": "property-1",
        "signal_type": "permit",
        "evidence_ref": "permit:1",
        "source": "empiredb",
        "observed_at": "2026-10-02T12:00:00+00:00",
        "truth_class": "OBSERVED",
        "data_backend": "empiredb",
    }
    row.update(overrides)
    return row


def test_property_observation_produces_inferred_opportunity_not_revenue():
    result = build_property_product_integration(
        tenant_id="tenant-a",
        observations=[observation()],
    )

    assert result["opportunity_count"] == 1
    assert result["opportunities"][0]["truth_class"] == "INFERRED"
    assert result["opportunities"][0]["buyer_intent"] == "UNKNOWN"
    assert result["commercial_offer"]["binding"] is False
    assert result["paid_proof"]["state"] == "UNKNOWN"
    assert result["revenue_recognition_performed"] is False
    assert result["outbound_performed"] is False
    assert result["execution_authority"] == "none"


def test_property_rejects_noncanonical_or_foreign_observations():
    result = build_property_product_integration(
        tenant_id="tenant-a",
        observations=[
            observation(data_backend="legacy"),
            observation(tenant_id="tenant-b", evidence_ref="permit:2"),
        ],
    )

    assert result["opportunity_count"] == 0
    reasons = {row["reason"] for row in result["rejected_observations"]}
    assert "canonical_evidence_required" in reasons
    assert "tenant_mismatch" in reasons
