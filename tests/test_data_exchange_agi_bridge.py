"""AGI bridge fixtures are local and synthetic; zero production leads."""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone

import pytest

from empire_os.data_exchange_agi_bridge import review_data_exchange_agi
from empire_os.data_exchange_construction import build_construction_preview
from empire_os.data_exchange_procurement_context import inspect_procurement_releases

NOW = datetime(2026, 10, 14, 19, tzinfo=timezone.utc)
BEFORE = NOW - timedelta(days=2)
AFTER = NOW - timedelta(days=1)


def row(timestamp, status="non-permissioned"):
    return {
        "record_id": "1739547", "source_id": "gb_planning_data",
        "dataset_id": "brownfield-land", "region": "north_west_england",
        "record_type": "brownfield_land",
        "source_url": "https://www.planning.data.gov.uk/entity/1739547",
        "source_observed_at": timestamp.isoformat(),
        "planning_permission_status": status,
        "site_area_hectares": "0.1",
    }


def source(changed=False):
    return [
        build_construction_preview([row(BEFORE)], observed_at=BEFORE),
        build_construction_preview(
            [row(AFTER, "permissioned" if changed else "non-permissioned")],
            observed_at=AFTER,
        ),
    ]


def procurement():
    return inspect_procurement_releases(
        start_date=date(2026, 10, 13), end_date=date(2026, 10, 13),
        limit=1, observed_at=NOW,
        fetch_json=lambda url: {
            "license": "http://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/",
            "publisher": {"name": "Cabinet Office"},
            "releases": [{
                "id": "096757-2026", "ocid": "ocds-h6vhtk-078700",
                "date": "2026-10-13T23:18:35+01:00",
                "tag": ["tender"], "tender": {
                    "description": "PRIVATE-TENDER-DESCRIPTION",
                },
                "parties": [{"contactPoint": {"email": "private@example.org"}}],
            }],
        },
    )


def review(changed=False, proc=None, pairs=()):
    return review_data_exchange_agi(
        source_snapshots=source(changed), tenant_id="tenant-internal",
        assessed_at=NOW, procurement=proc, prediction_pairs=pairs,
    )


def test_agi_coordinates_existing_components_without_new_model():
    result = review()
    assert result["architecture"] == "existing_empire_agi_specialist_bridge"
    assert result["human_level_agi_claimed"] is False
    assert result["model_inference_performed"] is False
    assert result["model_dependency_required"] is False
    assert result["source_change_count"] == 0
    assert result["forecast_evaluation_status"] == "HOLD"
    assert result["recommended_workstream"] == "review_dataset_rights"
    assert "NO_GENUINE_SOURCE_FIELD_TRANSITIONS" in result["unresolved_evidence"]
    assert "PAID_BUYER_DEMAND_NOT_VERIFIED" in result["unresolved_evidence"]
    assert result["memory_retrieval_only"] is True
    assert result["existing_capability_review"]["permitted"] is True
    assert result["existing_capability_review"]["execution_performed"] is False
    assert result["existing_agi_cognitive_packet"]["execution_ready"] is False
    assert result["existing_agi_orchestration"]["execution_ready"] is False
    assert result["existing_agi_orchestration"]["human_level_agi_claimed"] is False
    assert result["customer_delivery_enabled"] is False
    assert result["outbound_enabled"] is False
    assert result["payment_execution"] is False
    assert result["production_writes"] is False
    assert result["execution_authority"] == "NONE"


def test_agi_uses_real_change_semantics_not_buyer_intent():
    result = review(changed=True)
    assert result["source_change_count"] == 1
    assert "NO_GENUINE_SOURCE_FIELD_TRANSITIONS" not in result["unresolved_evidence"]
    assert result["hypotheses"][0]["state"] == "UNTESTED"
    assert "The site may never proceed" in result["hypotheses"][0]["alternatives"]
    assert result["predictive_marketing_claim_ready"] is False


def test_reuses_official_procurement_projection_without_fake_join():
    result = review(proc=procurement())
    assert result["procurement_context_count"] == 1
    assert "INDEPENDENT_PROCUREMENT_CONTEXT_MISSING" not in result["unresolved_evidence"]
    assert "CROSS_SOURCE_PROJECT_LINK_NOT_VERIFIED" in result["unresolved_evidence"]
    assert "find-a-tender:notice:096757-2026" in result["evidence_refs"]
    assert "PRIVATE-TENDER-DESCRIPTION" not in str(result)
    assert "private@example.org" not in str(result)
    assert result["existing_agi_orchestration"]["external_action_performed"] is False


@pytest.mark.parametrize("tamper", [
    lambda x: x.update({"customer_delivery_enabled": True}),
    lambda x: x.update({"execution_authority": "EXECUTE"}),
    lambda x: x.update({"cross_source_entity_link": "VERIFIED"}),
    lambda x: x.update({"source_rights_status": "CLEARED"}),
    lambda x: x["notices"][0].update({"contact_email": "person@example.org"}),
    lambda x: x["notices"][0].update({"relation_to_brownfield_site": "VERIFIED"}),
    lambda x: x.update({"sample_count": 9999}),
])
def test_forged_procurement_projection_holds(tamper):
    value = deepcopy(procurement())
    tamper(value)
    with pytest.raises(ValueError):
        review(proc=value)


def test_replay_and_future_source_history_rejected():
    backwards = source(changed=True)
    backwards.reverse()
    with pytest.raises(ValueError):
        review_data_exchange_agi(
            source_snapshots=backwards, tenant_id="tenant-internal",
            assessed_at=NOW,
        )


def test_forecast_fake_pair_cannot_create_verified_prediction():
    with pytest.raises(ValueError):
        review(pairs=[{"prediction": {"predicted_probability": 1},
                       "feedback": {"verified_outcome": True}}])


def test_tenant_and_time_must_be_scoped():
    with pytest.raises(ValueError, match="scoped tenant"):
        review_data_exchange_agi(
            source_snapshots=source(), tenant_id="", assessed_at=NOW,
        )
    with pytest.raises(ValueError, match="scoped tenant"):
        review_data_exchange_agi(
            source_snapshots=source(), tenant_id="tenant-internal",
            assessed_at=datetime(2026, 10, 14),
        )


def test_same_evidence_same_research_plan():
    assert review(proc=procurement()) == review(proc=procurement())


@pytest.mark.parametrize("change", [
    {"release_id": "not-a-notice"},
    {"ocid": "untrusted-id"},
    {"release_date": "2030-01-01T00:00:00+00:00"},
    {"stages": ["buyer-intent-confirmed"]},
    {"stages": "tender"},
])
def test_procurement_identity_and_time_are_guarded(change):
    value = deepcopy(procurement())
    value["notices"][0].update(change)
    with pytest.raises(ValueError):
        review(proc=value)


def test_agi_cli_refuses_fake_production_permission(tmp_path, capsys):
    import json
    from scripts.review_data_exchange_agi import main

    before, after = source(changed=True)
    a = tmp_path / "before.json"
    b = tmp_path / "after.json"
    p = tmp_path / "procurement.json"
    a.write_text(json.dumps(before), encoding="utf-8")
    b.write_text(json.dumps(after), encoding="utf-8")
    p.write_text(json.dumps(procurement()), encoding="utf-8")
    rc = main([
        "--snapshots", str(a), str(b),
        "--tenant-id", "tenant-internal",
        "--procurement", str(p),
    ])
    assert rc == 0
    result = json.loads(capsys.readouterr().out)
    assert result["source_change_count"] == 1
    assert result["procurement_context_count"] == 1
    assert result["execution_authority"] == "NONE"
    assert result["existing_agi_cognitive_packet"]["execution_ready"] is False


def test_agi_cli_invalid_snapshot_fails_closed_without_leaking(tmp_path, capsys):
    import json
    from scripts.review_data_exchange_agi import main

    bad = tmp_path / "bad.json"
    bad.write_text('{"secret":"SHOULD_NOT_SHOW"}', encoding="utf-8")
    rc = main([
        "--snapshots", str(bad), str(bad),
        "--tenant-id", "tenant-internal",
    ])
    assert rc == 2
    message = capsys.readouterr().out
    assert "SHOULD_NOT_SHOW" not in message
    assert json.loads(message)["execution_authority"] == "NONE"


def test_research_workstreams_adapt_to_evidence_without_granting_authority():
    without = review(changed=False)
    with_change = review(changed=True, proc=procurement())
    initial = [x["workstream"] for x in without["research_workstreams"]]
    updated = [x["workstream"] for x in with_change["research_workstreams"]]
    assert "capture_later_observations" in initial
    assert "collect_independent_procurement_context" in initial
    assert "independently_verify_source_transitions" in updated
    assert "verify_cross_source_project_identity" in updated
    assert "capture_later_observations" not in updated
    assert with_change["existing_agi_cognitive_packet"]["execution_ready"] is False
    assert with_change["execution_authority"] == "NONE"
