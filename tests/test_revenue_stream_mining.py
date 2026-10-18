"""Existing EmpireOS data streams -> deterministic zero-cost department reviews."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import json
import pytest

from empire_os.opportunity_evidence_router import ROUTES
from empire_os.quant_brain import _DECISION_PACKET_REQUIRED
from empire_os.revenue_stream_mining import (
    SOURCES, build_revenue_stream_mining, enqueue_existing_department_mining,
)

def write(root, stream, source):
    relative = SOURCES[stream][0]
    file = root / relative
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(source), encoding="utf-8")
    return file

def fixture_sources(root, *, at=None):
    now = at or datetime.now(timezone.utc)
    inbox = {}
    for num, origin in enumerate(("permits_nyc", "reddit")):
        key = sha256(f"original-event-{num}".encode()).hexdigest()
        inbox[key] = {
            "signal_id": key, "source": origin, "seen_count": 1,
            "created_at": now.isoformat(), "last_seen_at": now.isoformat(),
            "execution_authority": "none",
            "email": "private.person@example.com",
            "name": "Private Person",
            "raw": {"private_raw": "secret-content"},
        }
    write(root, "acquisition", inbox)
    selected = [
        "independent_evidence_required",
        "buyer_intent_normalized_score_required",
        "margin_potential_normalized_score_required",
    ]
    routes = [
        dict(ROUTES[name], blocker=name) for name in selected
    ]
    router = {
        "schema_version": SOURCES["opportunity_routes"][1],
        "mode": "OBSERVE", "execution_authority": "none",
        "generated_at": now.isoformat(),
        "opportunity_count": 1,
        "items": [{
            "opportunity_key": "solar-case",
            "tenant_id": None,
            "execution_authority": "none",
            "routes": routes, "route_count": len(routes),
            "private_business_email": "buyer-secret@example.com",
        }],
    }
    write(root, "opportunity_routes", router)
    missing = list(_DECISION_PACKET_REQUIRED)
    quant = {
        "schema_version": SOURCES["quant"][1],
        "mode": "OBSERVE", "execution_authority": "none",
        "generated_at": now.isoformat(),
        "candidate_count": 1,
        "available_decision_packet_count": 0,
        "unavailable_decision_packet_count": 1,
        "missing_field_counts": {name: 1 for name in missing},
        "items": [{
            "opportunity_key": "solar-case",
            "tenant_id": None, "prediction_ref": None,
            "decision_packet": {
                "status": "UNAVAILABLE", "missing_fields": missing,
            },
            "private_buyer": "private_name",
        }],
    }
    write(root, "quant", quant)
    competitor = {
        "schema_version": SOURCES["competitor"][1],
        "mode": "OBSERVE", "execution_authority": "none",
        "generated_at": (now - timedelta(days=30)).isoformat(),
        "canonical_company_count": 42,
        "buyer_intent_inferred": False,
        "commercial_intent_inferred": False,
        "revenue_opportunity_inferred": False,
        "private_company_list": ["company@example.org"],
    }
    write(root, "competitor", competitor)
    return inbox, router, quant, competitor, now

def test_mines_existing_sources_into_exact_specialist_lanes(tmp_path):
    fixture_sources(tmp_path)
    result = build_revenue_stream_mining(tmp_path)
    assert result["status"] == "MINING_REVIEW_READY"
    assert result["source_count"] == 4
    assert result["lane_count"] == 5
    assert result["worker_dispatched"] is False
    assert result["cross_lane_counts_are_not_additive"] is True
    statuses = {name: row["status"] for name, row in result["sources"].items()}
    assert statuses == {
        "acquisition": "OBSERVED", "opportunity_routes": "FRESH",
        "quant": "FRESH", "competitor": "STALE",
    }
    lanes = {row["stream"]: row for row in result["department_lanes"]}
    assert lanes["acquisition"]["counts"] == {
        "signal_inventory": 2, "new_first_observations_24h": 2,
        "permit_source_signals": 1, "other_source_signals": 1,
    }
    assert lanes["public_opportunity"]["counts"]["public_blocker_count"] == 1
    assert lanes["commercial_opportunity"]["counts"]["commercial_observation_blocker_count"] == 1
    assert lanes["quant_economics"]["counts"]["missing_quant_economics_count"] == 1
    assert lanes["quant_economics"]["department"] == "data_quant"
    assert lanes["commercial_opportunity"]["department"] == "business_development"
    assert lanes["competitor"]["counts"] == {}
    text = json.dumps(result)
    for secret in ("private.person@", "buyer-secret@", "private_name",
                   "secret-content", "company@example.org"):
        assert secret not in text
    assert result["payment_authorized"] is False
    assert result["commercial_execution_authorized"] is False

def test_existing_work_queue_delivery_is_idempotent_and_keeps_authority(tmp_path):
    fixture_sources(tmp_path)
    report = build_revenue_stream_mining(tmp_path)
    out = enqueue_existing_department_mining(
        tmp_path, report, max_jobs=4, allow_noncanonical_test=True,
    )
    assert out["status"] == "ROUTED_TO_EXISTING_DEPARTMENT_QUEUE"
    assert out["jobs_new"] == 4
    assert "competitor" in out["skipped_lanes"]
    repeat = enqueue_existing_department_mining(
        tmp_path, report, max_jobs=4, allow_noncanonical_test=True,
    )
    assert repeat["jobs_new"] == 0
    assert repeat["jobs_duplicate"] == 4
    jobs = list((tmp_path / "runtime/departments/work/ready").glob("*.json"))
    assert len(jobs) == 4
    for path in jobs:
        job = json.loads(path.read_text())
        assert job["authority"] == "observe"
        assert job["intelligence_request"]["budget"]["requested_external_cost_cents"] == 0
        assert job["intelligence_request"]["budget"]["requested_model_tokens"] == 0
        assert "private.person" not in json.dumps(job)
        assert "buyer-secret@" not in json.dumps(job)
    assert out["money_spent"] is False
    assert out["new_queue_created"] is False

def test_read_only_review_never_creates_queue(tmp_path):
    fixture_sources(tmp_path)
    assert build_revenue_stream_mining(tmp_path)["lane_count"] == 5
    assert not (tmp_path/"runtime/departments/work").exists()

def test_duplicate_event_and_tenant_scoped_record_are_held(tmp_path):
    inbox, router, _, _, _ = fixture_sources(tmp_path)
    key = next(iter(inbox))
    inbox["other-key"] = deepcopy(inbox[key])
    write(tmp_path, "acquisition", inbox)
    out = build_revenue_stream_mining(tmp_path)
    assert out["sources"]["acquisition"]["status"] == "UNTRUSTED"
    assert out["sources"]["acquisition"]["aggregate"] is None
    router["items"][0]["tenant_id"] = "private-tenant"
    write(tmp_path, "opportunity_routes", router)
    out = build_revenue_stream_mining(tmp_path)
    assert out["sources"]["opportunity_routes"]["status"] == "UNTRUSTED"

def test_stale_or_future_sources_do_not_claim_fresh_observations(tmp_path):
    _, routes, quant, _, now = fixture_sources(tmp_path)
    routes["generated_at"] = (now + timedelta(minutes=5)).isoformat()
    write(tmp_path, "opportunity_routes", routes)
    quant["generated_at"] = (now - timedelta(days=3)).isoformat()
    write(tmp_path, "quant", quant)
    out = build_revenue_stream_mining(tmp_path, as_of=now)
    assert out["sources"]["opportunity_routes"]["status"] == "FUTURE_HELD"
    assert out["sources"]["quant"]["status"] == "STALE"
    assert out["sources"]["quant"]["aggregate"] is None

def test_forged_lane_cannot_create_department_job(tmp_path):
    fixture_sources(tmp_path)
    report = build_revenue_stream_mining(tmp_path)
    altered = deepcopy(report)
    altered["department_lanes"][0]["counts"]["signal_inventory"] = 300000
    with pytest.raises(ValueError, match="drift or tampering"):
        enqueue_existing_department_mining(
            tmp_path, altered, allow_noncanonical_test=True,
        )
    assert not (tmp_path/"runtime/departments/work").exists()

def test_noncanonical_dispatch_refused_without_test_flag(tmp_path):
    fixture_sources(tmp_path)
    with pytest.raises(PermissionError, match="ONLY_CANONICAL"):
        enqueue_existing_department_mining(
            tmp_path, build_revenue_stream_mining(tmp_path),
        )
    assert not (tmp_path/"runtime/departments/work").exists()

def test_source_missing_does_not_invent_zero_counts(tmp_path):
    result = build_revenue_stream_mining(tmp_path)
    assert result["status"] == "SOURCE_REFRESH_REQUIRED"
    assert all(lane["counts"] == {} for lane in result["department_lanes"])
    assert result["source_count"] == 4
    assert result["worker_dispatched"] is False


@pytest.mark.parametrize("field,forgery", [
    ("source_ref", "runtime:private:customer:secrets"),
    ("department", "finance"),
    ("next_internal_action", "send_email_to_buyer"),
    ("cost_budget_cents", 100),
    ("external_execution_authorized", True),
])
def test_untrusted_handoff_fields_rejected_even_when_digest_matches(
    tmp_path, field, forgery,
):
    fixture_sources(tmp_path)
    report = build_revenue_stream_mining(tmp_path)
    altered = deepcopy(report)
    altered["department_lanes"][0][field] = forgery
    with pytest.raises(ValueError, match="drift or tampering"):
        enqueue_existing_department_mining(
            tmp_path, altered, allow_noncanonical_test=True,
        )
    assert not (tmp_path/"runtime/departments/work").exists()
