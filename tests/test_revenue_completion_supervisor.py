from __future__ import annotations

import json
from pathlib import Path

from empire_os.revenue_completion_supervisor import build_snapshot, buyer_status, tam_status


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_tam_status_reports_completed_job(tmp_path):
    runtime = tmp_path / "coder"
    _write(runtime / "jobs/completed/job.json", {
        "id": "job-1",
        "task_id": "task-1",
        "attempts": 1,
        "status": "COMPLETED",
    })
    result = tam_status(runtime)
    assert result["state"] == "COMPLETED"
    assert result["job_id"] == "job-1"
    assert result["task_id"] == "task-1"


def test_buyer_status_surfaces_only_genuine_review_ready(tmp_path):
    deferred = tmp_path / "deferred.json"
    materializer = tmp_path / "materializer.json"
    _write(deferred, {
        "p1": {
            "status": "pending",
            "reason": "no_bound_contact",
            "priority_score": 95,
            "attempts": 2,
            "target_people": [{"name": "A", "title": "Founder"}],
        },
        "p2": {
            "status": "deferred",
            "reason": "site_timeout",
            "priority_score": 95,
            "attempts": 12,
        },
    })
    _write(materializer, {
        "eligible": 2,
        "deferred_enrichment": 1,
        "outcomes": [
            {
                "prospect_id": "p1",
                "decision_name": "A",
                "decision_title": "Founder",
                "preferred_email": "a@example.com",
                "review_ready": True,
                "outreach_ready": True,
            },
            {
                "prospect_id": "p2",
                "decision_name": "B",
                "preferred_email": None,
                "review_ready": True,
                "outreach_ready": False,
            },
        ],
    })
    result = buyer_status(deferred, materializer)
    assert result["evidence_rich_high_priority"] == 1
    assert result["retry_saturated"] == 1
    assert result["genuine_review_ready_count"] == 1
    assert result["genuine_review_ready"][0]["prospect_id"] == "p1"


def test_supervisor_systemd_is_observe_only():
    root = Path(__file__).resolve().parents[1]
    service = (
        root / "deploy/systemd/empire-revenue-completion-supervisor.service"
    ).read_text()
    timer = (
        root / "deploy/systemd/empire-revenue-completion-supervisor.timer"
    ).read_text()
    assert "run_revenue_completion_supervisor.py" in service
    assert "ReadWritePaths=/srv/empire_os/runtime" in service
    assert "OnUnitActiveSec=2min" in timer


def test_tam_coder_timer_is_plan_only_and_bounded():
    root = Path(__file__).resolve().parents[1]
    service = (
        root / "deploy/systemd/empire-tam-coder-plan.service"
    ).read_text()
    timer = (
        root / "deploy/systemd/empire-tam-coder-plan.timer"
    ).read_text()
    assert "scripts/empire_coder_worker.py" in service
    assert "runtime/coder_tam_lane" in service
    assert "--max-attempts 3" in service
    assert "ReadWritePaths=/srv/empire_os/runtime" in service
    assert "OnUnitActiveSec=5min" in timer


def test_build_snapshot_classifies_missing_tam_runtime_as_evidence_unavailable(monkeypatch, tmp_path):
    import empire_os.revenue_completion_supervisor as supervisor

    monkeypatch.setattr(supervisor, "DEFAULT_TAM_RUNTIME", tmp_path / "coder")
    monkeypatch.setattr(supervisor, "DEFAULT_TAM_SNAPSHOT", tmp_path / "missing.json")
    monkeypatch.setattr(supervisor, "buyer_status", lambda: {
        "genuine_review_ready_count": 0,
        "evidence_rich_high_priority": 0,
    })
    _write(tmp_path / "coder/jobs/failed/job.json", {
        "id": "job-1", "task_id": "task-1", "attempts": 3,
        "status": "FAILED", "error": "timeout",
    })
    result = build_snapshot()
    assert "tam_runtime_evidence_unavailable" in result["blockers"]
    assert "tam_planner_failed" not in result["blockers"]
    assert result["tam_runtime"]["available"] is False


def test_build_snapshot_keeps_failed_planner_as_history_when_runtime_exists(monkeypatch, tmp_path):
    import empire_os.revenue_completion_supervisor as supervisor

    monkeypatch.setattr(supervisor, "DEFAULT_TAM_RUNTIME", tmp_path / "coder")
    snapshot = tmp_path / "tam.json"
    from datetime import datetime, timezone
    _write(snapshot, {
        "schema_version": "empire.tam-market-intelligence.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "OBSERVE",
        "source": "empiredb_restricted_tam_reader",
        "canonical_data": True,
        "tenant_source_scope_verified": False,
        "data_scope": "PLATFORM_MARKET_RESEARCH_ONLY",
        "tenant_id": "test-platform",
        "market_scope_count": 1,
        "market_scopes": [{"industry": "roofing", "country_code": "US",
                           "observed_entity_count": 1,
                           "new_industry": False, "new_country": True,
                           "tam_state": "UNKNOWN", "tam_entity_count": None}],
        "source_row_count": 1,
        "opportunity_classes": [{
            "opportunity_key": "tam:test-platform:new_country:roofing:US",
            "opportunity_class": "new_country", "industry": "roofing",
            "country_code": "US", "observed_entity_count": 1,
            "tam_state": "UNKNOWN", "tam_entity_count": None,
            "evidence_refs": ["registry:test"], "decision": "research",
            "buyer_intent_proven": False, "demand_proven": False,
            "commercial_terms_verified": False, "revenue_verified": False,
            "execution_authority": "none",
        }],
        "execution_authority": "none",
        "tam_inferred_from_observed_roster": False,
        "buyer_intent_inferred": False,
        "demand_inferred": False,
        "pricing_inferred": False,
        "revenue_inferred": False,
        "prospect_created": False,
        "outreach_enabled": False,
        "external_execution": False,
    })
    monkeypatch.setattr(supervisor, "DEFAULT_TAM_SNAPSHOT", snapshot)
    monkeypatch.setattr(supervisor, "buyer_status", lambda: {
        "genuine_review_ready_count": 0,
        "evidence_rich_high_priority": 0,
    })
    _write(tmp_path / "coder/jobs/failed/job.json", {
        "id": "job-1", "task_id": "task-1", "attempts": 3,
        "status": "FAILED", "error": "timeout",
    })
    result = build_snapshot()
    assert "tam_planner_failed_historical" not in result["blockers"]
    assert "tam_runtime_evidence_unavailable" not in result["blockers"]
    assert result["tam_diagnostics"]["historical_planner_failure"] is True
    assert result["tam_diagnostics"]["canonical_source_separate_from_llm_planner"] is True
    assert result["tam_runtime"]["available"] is True
    assert result["tam_runtime"]["opportunity_class_count"] == 1
    assert result["tam_reader_prerequisites"]["isolated_tam_release_stage"] == (
        "CANONICAL_RESEARCH_SNAPSHOT_VERIFIED_OBSERVE"
    )
    assert result["tam_reader_prerequisites"]["isolated_tam_data_snapshot_verified"] is True
    assert result["tam_next_evidence_task"] == (
        "VALIDATE_DOWNSTREAM_RADAR_EVIDENCE_CONSUMPTION"
    )



def test_historical_tam_ollama_timeout_is_not_an_active_retry(tmp_path):
    from empire_os.revenue_completion_supervisor import tam_status
    _write(tmp_path / "jobs/failed/job.json", {
        "id": "j-oct2", "status": "FAILED", "attempts": 3,
        "updated_at": "2026-10-02T19:20:37+00:00",
        "error": "RuntimeError:ollama_request_failed:TimeoutError:max_attempts_exhausted",
    })
    result=tam_status(tmp_path)
    assert result["state"]=="FAILED"
    assert result["active_job"] is False
    assert result["operational_state"]=="IDLE_HISTORIC_TERMINAL_FAILURE"
    assert result["last_terminal_failure_reason"]=="MODEL_INFERENCE_TIMEOUT"
    assert result["terminal_failure_history_count"]==1
    assert result["attempts"]==3


def test_tam_snapshot_truth_refuses_empty_schema_label_stale_and_send_authority():
    from datetime import datetime, timedelta, timezone
    from empire_os.revenue_completion_supervisor import tam_snapshot_truth
    now=datetime(2026,10,10,12,0,tzinfo=timezone.utc)
    sample={
        "schema_version":"empire.tam-market-intelligence.v1",
        "mode":"OBSERVE","source":"empiredb_restricted_tam_reader",
        "canonical_data":True,
        "tenant_source_scope_verified":False,
        "data_scope":"PLATFORM_MARKET_RESEARCH_ONLY",
        "tenant_id":"research-platform",
        "generated_at":now.isoformat(),"market_scope_count":1,
        "market_scopes":[{
            "industry":"roofing","country_code":"US",
            "observed_entity_count":1,
            "tam_state":"UNKNOWN","tam_entity_count":None,
        }],
        "source_row_count":1,"opportunity_classes":[],
        "execution_authority":"none",
        "tam_inferred_from_observed_roster":False,
        "buyer_intent_inferred":False,"demand_inferred":False,
        "pricing_inferred":False,"revenue_inferred":False,
        "prospect_created":False,"outreach_enabled":False,
        "external_execution":False,
    }
    good=tam_snapshot_truth(sample,now=now)
    assert good["available"] is True
    assert good["market_scope_count"]==1
    assert good["tam_counts_inferred_from_roster"] is False
    for edits,reason in (
        ({"outreach_enabled":True},"SNAPSHOT_CONTRACT_NOT_VERIFIED"),
        ({"tenant_source_scope_verified":True},"SNAPSHOT_CONTRACT_NOT_VERIFIED"),
        ({"data_scope":"TENANT_CUSTOMER_RUNTIME"},"SNAPSHOT_CONTRACT_NOT_VERIFIED"),
        ({"source":"unknown_web_scrape"},"SNAPSHOT_CONTRACT_NOT_VERIFIED"),
        ({"market_scope_count":50},"SNAPSHOT_CONTRACT_NOT_VERIFIED"),
        ({"execution_authority":"internal_write"},"SNAPSHOT_CONTRACT_NOT_VERIFIED"),
        ({"generated_at":(now-timedelta(days=4)).isoformat()},
         "SNAPSHOT_STALE_REQUIRES_RESTRICTED_REFRESH"),
        ({"generated_at":(now+timedelta(hours=2)).isoformat()},
         "SNAPSHOT_CLOCK_IN_FUTURE"),
    ):
        actual=tam_snapshot_truth({**sample,**edits},now=now)
        assert actual["available"] is False
        assert actual["reason_code"]==reason
        assert actual["opportunity_class_count"]==0
    assert tam_snapshot_truth({"schema_version":sample["schema_version"]},
                              now=now)["available"] is False


def test_tam_prerequisites_are_boolean_checks_without_secret_values():
    from empire_os.revenue_completion_supervisor import tam_reader_prerequisites
    good={
        "EMPIRE_TAM_TENANT_ID":"tenant-secret-123",
        "EMPIRE_TAM_ACTIVE_INDUSTRIES":"roofing,solar",
        "EMPIRE_TAM_ACTIVE_COUNTRIES":"US,GB",
        "EMPIRE_INTELLIGENCE_MATERIALIZER_DSN":"postgresql://secret:secret@localhost/empiredb",
    }
    ready=tam_reader_prerequisites(good)
    assert ready["runtime_environment_configured"] is False
    assert ready["scope_environment_configured"] is True
    assert ready["isolated_tam_credential_live_verified"] is False
    assert ready["isolated_tam_release_stage"]=="PREPARED_NOT_PRODUCTION_ACTIVATED"
    assert ready["missing_runtime_environment_keys"]==[]
    assert ready["restricted_empiredb_sql_reader_live_verified"] is False
    assert ready["auto_planner_retry_authorized"] is False
    assert "secret" not in str(ready)
    missing=tam_reader_prerequisites({})
    assert missing["runtime_environment_configured"] is False
    assert len(missing["missing_runtime_environment_keys"])==3



def test_current_tam_queue_activity_outweighs_older_failed_history(tmp_path):
    from empire_os.revenue_completion_supervisor import tam_status
    _write(tmp_path / "jobs/failed/old.json", {
        "status":"FAILED","error":"TimeoutError","attempts":3
    })
    _write(tmp_path / "jobs/pending/new.json", {
        "status":"PENDING","attempts":0,"id":"new"
    })
    result=tam_status(tmp_path)
    assert result["state"]=="PENDING"
    assert result["active_job"] is True
    assert result["operational_state"]=="ACTIVE_PLAN_JOB"
    assert result["terminal_failure_history_count"]==1
    assert result["last_terminal_failure_reason"]=="MODEL_INFERENCE_TIMEOUT"


def test_supervisor_due_count_excludes_repeated_saturated_retries(tmp_path):
    deferred = tmp_path / "deferred.json"
    materializer = tmp_path / "materializer.json"
    from datetime import datetime, timedelta, timezone
    expired = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    _write(deferred, {
        "site": {
            "status": "deferred", "reason": "site_timeout",
            "priority_score": 95, "attempts": 8,
            "next_retry_at": expired,
        },
        "person": {
            "status": "pending", "reason": "no_bound_contact",
            "priority_score": 95, "attempts": 32,
            "target_people": [{"name": "Jane Buyer", "title": "Founder"}],
            "next_retry_at": expired,
        },
        "fresh": {
            "status": "pending", "reason": "no_contact_evidence",
            "priority_score": 40, "attempts": 2,
            "next_retry_at": expired,
        },
    })
    _write(materializer, {})
    r = buyer_status(deferred, materializer)
    assert r["due_now"] == 1
    assert r["evidence_parked_count"] == 2
    assert r["high_priority_parked_count"] == 2
    assert r["genuine_review_ready_count"] == 0
    assert r["retry_saturated"] == 2


def test_supervisor_next_action_avoids_repeated_parked_searches(
    monkeypatch, tmp_path,
):
    import empire_os.revenue_completion_supervisor as supervisor
    monkeypatch.setattr(supervisor, "DEFAULT_TAM_RUNTIME", tmp_path/"coder")
    monkeypatch.setattr(supervisor, "DEFAULT_TAM_SNAPSHOT", tmp_path/"no-tam.json")
    monkeypatch.setattr(supervisor, "buyer_status", lambda: {
        "genuine_review_ready_count": 0,
        "evidence_rich_high_priority": 17,
        "due_now": 0,
        "evidence_parked_count": 2051,
        "backlog_health": "CRITICAL",
    })
    r = supervisor.build_snapshot()
    assert r["next_action"] == "await_automatic_first_party_evidence_refresh"
    assert r["buyers"]["evidence_parked_count"] == 2051
    assert "buyer_enrichment_backlog_critical" in r["blockers"]
    assert r["outbound_sent"] is False
    assert r["execution_authority"] == "none"
