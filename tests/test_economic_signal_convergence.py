from copy import deepcopy

from empire_os.opportunity_source_convergence import (
    economic_signal_candidates,
)


TENANT = "tenant-alpha"


def signal(signal_type="market_gap", **changes):
    base = {
        "schema_version": "empire.economic-signal.v1",
        "signal_id": "economic_signal_" + ("a" * 64),
        "tenant_id": TENANT,
        "tenant_binding_ref": "canonical:tenant-binding:alpha:entity",
        "entity_id": "11111111-1111-1111-1111-111111111111",
        "source_id": "22222222-2222-2222-2222-222222222222",
        "signal_type": signal_type,
        "signal_domain": "economic_opportunity",
        "observed_at": "2026-10-06T09:00:00+00:00",
        "strength": 0.8,
        "confidence": 0.9,
        "evidence_refs": ["canonical:evidence:1"],
        "payload": {"scope": "roofing:denver"},
        "truth_class": "OBSERVED",
        "data_backend": "empiredb",
        "execution_authority": "none",
        "outreach_authority": "none",
        "calls_authority": "none",
        "traffic_authority": "none",
        "commercial_authority": "none",
        "payment_authority": "none",
        "revenue_recognition_authority": "none",
    }
    base.update(changes)
    return base


def test_all_four_signal_families_converge():
    mapping = {
        "revenue_leak": "revenue_recovery",
        "idle_asset": "idle_asset_activation",
        "market_gap": "market_gap",
        "idle_waste": "waste_recovery",
    }

    for index, (source_type, opportunity_type) in enumerate(
        mapping.items()
    ):
        candidate = signal(
            source_type,
            signal_id="economic_signal_" + str(index) * 64,
        )

        result = economic_signal_candidates(
            [candidate],
            tenant_id=TENANT,
        )

        assert len(result) == 1
        assert result[0]["opportunity_type"] == opportunity_type


def test_candidate_preserves_provenance():
    result = economic_signal_candidates(
        [signal()],
        tenant_id=TENANT,
    )[0]

    assert result["source_family"] == "economic_signal_fabric"
    assert result["source_signal_id"].startswith("economic_signal_")
    assert result["entity_id"]
    assert result["source_id"]
    assert result["evidence_refs"] == ["canonical:evidence:1"]


def test_observation_does_not_invent_economics():
    result = economic_signal_candidates(
        [signal()],
        tenant_id=TENANT,
    )[0]

    assert result["buyer_demand_verified"] is False
    assert result["commercial_readiness_verified"] is False
    assert result["economics_verified"] is False
    assert result["payout_cents"] is None
    assert result["expected_revenue_cents"] is None
    assert result["recognized_revenue_cents"] is None


def test_candidate_is_review_only_not_factory_ready():
    result = economic_signal_candidates(
        [signal()],
        tenant_id=TENANT,
    )[0]

    assert result["evidence_complete"] is True
    assert result["factory_ready"] is False
    assert result["review_required"] is True


def test_all_authorities_remain_none():
    result = economic_signal_candidates(
        [signal()],
        tenant_id=TENANT,
    )[0]

    for field in (
        "execution_authority",
        "outreach_authority",
        "calls_authority",
        "traffic_authority",
        "commercial_authority",
        "payment_authority",
        "revenue_recognition_authority",
    ):
        assert result[field] == "none"


def test_cross_tenant_signal_fails_closed():
    result = economic_signal_candidates(
        [signal(tenant_id="tenant-other")],
        tenant_id=TENANT,
    )
    assert result == []


def test_missing_tenant_binding_fails_closed():
    result = economic_signal_candidates(
        [signal(tenant_binding_ref="")],
        tenant_id=TENANT,
    )
    assert result == []


def test_non_observed_signal_fails_closed():
    result = economic_signal_candidates(
        [signal(truth_class="PREDICTED")],
        tenant_id=TENANT,
    )
    assert result == []


def test_noncanonical_backend_fails_closed():
    result = economic_signal_candidates(
        [signal(data_backend="sqlite")],
        tenant_id=TENANT,
    )
    assert result == []


def test_authority_expansion_fails_closed():
    result = economic_signal_candidates(
        [signal(execution_authority="outbound")],
        tenant_id=TENANT,
    )
    assert result == []


def test_duplicate_signal_collapses():
    original = signal()
    duplicate = deepcopy(original)

    result = economic_signal_candidates(
        [original, duplicate],
        tenant_id=TENANT,
    )

    assert len(result) == 1


def test_unknown_signal_family_is_not_promoted():
    result = economic_signal_candidates(
        [signal(signal_type="magic_money")],
        tenant_id=TENANT,
    )
    assert result == []


def test_payload_commercial_claim_cannot_change_candidate_truth():
    candidate = signal(
        payload={
            "scope": "roofing:denver",
            "expected_revenue_cents": 999999999,
            "buyer_demand_verified": True,
        }
    )

    result = economic_signal_candidates(
        [candidate],
        tenant_id=TENANT,
    )[0]

    assert result["expected_revenue_cents"] is None
    assert result["buyer_demand_verified"] is False
