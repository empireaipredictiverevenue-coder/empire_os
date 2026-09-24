from pathlib import Path

import empire_os.enterprise_contact_repair as repair


ROOT = Path(__file__).resolve().parents[1]


def test_failure_classifier_distinguishes_safe_repair_classes():
    assert repair.classify_failure(
        "POST rpc -> HTTP 504: timeout"
    ) == "TRANSIENT_INFRA"
    assert repair.classify_failure(
        "target_identity_mismatch"
    ) == "DATA_QUALITY"
    assert repair.classify_failure(
        "AssertionError FAILED tests/test_buyer_discovery.py::test_x"
    ) == "CODE_DEFECT"
    assert repair.classify_failure(
        "FAILED tests/test_timeout_logic.py::test_x - AssertionError"
    ) == "CODE_DEFECT"
    assert repair.classify_failure(
        "RuntimeError: missing required runtime env: "
        "SUPABASE_SERVICE_KEY,SUPABASE_URL"
    ) == "RUNTIME_ENV_CONTEXT"
    assert repair.classify_failure(
        "unclassified strange condition"
    ) == "UNKNOWN"


def test_failed_pytest_nodes_are_extracted_for_targeted_verification():
    log = """
FAILED tests/test_buyer_discovery.py::test_one - AssertionError
FAILED tests/test_buyer_probe_worker.py::test_two - AssertionError
"""
    assert repair._failing_tests(log) == [
        "tests/test_buyer_discovery.py::test_one",
        "tests/test_buyer_probe_worker.py::test_two",
    ]


def test_incident_record_is_fail_closed(monkeypatch, tmp_path):
    incident = tmp_path / "incident.json"
    monkeypatch.setattr(repair, "INCIDENT_PATH", incident)

    payload = repair.record_incident(
        kind="test_failure",
        log_text=(
            "FAILED tests/test_enterprise_contact_intelligence.py::test_x "
            "- AssertionError"
        ),
        command="pytest",
        returncode=1,
        base_head="abc123",
    )

    assert payload["classification"] == "CODE_DEFECT"
    assert payload["status"] == "OPEN"
    assert payload["base_head"] == "abc123"
    assert payload["live_outbound_send"] is False
    assert payload["payment_action"] is False
    assert payload["actual_revenue"] is False
    assert incident.exists()


def test_autonomous_code_repair_scope_is_narrow():
    assert "empire_os/buyer_discovery.py" in repair.ALLOWED_REPAIR_PATHS
    assert (
        "empire_os/enterprise_contact_intelligence.py"
        in repair.ALLOWED_REPAIR_PATHS
    )
    forbidden = (
        "deploy/systemd/empire-outbound-governor.service",
        "supabase/migrations/example.sql",
        "empire_os/payment_verifier.py",
        "recovery/legacy.py",
        "toop/tool.py",
    )
    assert not set(forbidden) & repair.ALLOWED_REPAIR_PATHS


def test_repair_controller_uses_isolated_worktree_and_compare_swap_guards():
    source = (
        ROOT / "empire_os/enterprise_contact_repair.py"
    ).read_text()
    assert "create_isolated(" in source
    assert "approved=True" in source
    assert "main_checkout_dirty" in source
    assert "incident_base_head_changed" in source
    assert "coder repair exceeded two-file change budget" in source
    assert "git_add_failed" in source
    assert '"merge", "--ff-only"' in source
    assert '"push",' in source
    assert "coder repair attempted authority expansion" in source
    assert "coder repair attempted to remove a test assertion" in source


def test_repair_systemd_is_internal_observe_only():
    service = (
        ROOT
        / "deploy/systemd/empire-enterprise-contact-repair.service"
    ).read_text()
    timer = (
        ROOT
        / "deploy/systemd/empire-enterprise-contact-repair.timer"
    ).read_text()

    assert "User=ubuntu" in service
    assert "EMPIRE_AUTONOMOUS_MODE=OBSERVE" in service
    assert "run_enterprise_contact_repair.py" in service
    assert "OnUnitActiveSec=10min" in timer
    assert "Persistent=true" in timer
    assert "outbound" not in service.lower()
    assert "payment" not in service.lower()


def test_code_repair_budget_quarantines_after_three_attempts(
    monkeypatch,
    tmp_path,
):
    incident = tmp_path / "incident.json"
    state = tmp_path / "state.json"
    latest = tmp_path / "latest.json"
    runtime = tmp_path / "runtime"
    runtime.mkdir()

    incident.write_text(
        """{
          "fingerprint": "same-failure",
          "classification": "CODE_DEFECT",
          "status": "OPEN",
          "log_tail": "AssertionError FAILED tests/test_x.py::test_x"
        }\n"""
    )
    state.write_text(
        """{
          "last_fingerprint": "same-failure",
          "last_status": "CODER_REPAIR_FAILED",
          "repair_attempts": 3
        }\n"""
    )

    monkeypatch.setattr(repair, "INCIDENT_PATH", incident)
    monkeypatch.setattr(repair, "STATE_PATH", state)
    monkeypatch.setattr(repair, "LATEST_PATH", latest)
    monkeypatch.setattr(repair, "RUNTIME", runtime)
    monkeypatch.setattr(
        repair,
        "_repair_code_incident",
        lambda _incident: (_ for _ in ()).throw(
            AssertionError("repair must not run after budget exhaustion")
        ),
    )

    result = repair.run_repair_cycle()
    assert result["status"] == "QUARANTINED_REPAIR_EXHAUSTED"
    assert result["repair_attempts"] == 3
    assert result["actual_revenue"] is False


def test_resolved_incident_does_not_hide_new_runtime_failure(
    monkeypatch,
    tmp_path,
):
    incident = tmp_path / "incident.json"
    state = tmp_path / "state.json"
    latest = tmp_path / "latest.json"
    runtime = tmp_path / "runtime"
    runtime.mkdir()

    incident.write_text(
        """{
          "fingerprint": "old",
          "classification": "CODE_DEFECT",
          "status": "RESOLVED"
        }\n"""
    )
    (runtime / "enterprise_contact_intelligence_latest.json").write_text(
        """{
          "error_count": 1,
          "errors": [{"error": "HTTP 504: timeout"}]
        }\n"""
    )

    monkeypatch.setattr(repair, "INCIDENT_PATH", incident)
    monkeypatch.setattr(repair, "STATE_PATH", state)
    monkeypatch.setattr(repair, "LATEST_PATH", latest)
    monkeypatch.setattr(repair, "RUNTIME", runtime)
    monkeypatch.setattr(
        repair,
        "_git",
        lambda *args, **kwargs: type(
            "Result",
            (),
            {"stdout": "abc123\n", "stderr": "", "returncode": 0},
        )(),
    )
    monkeypatch.setattr(
        repair,
        "_retry_runtime_sync",
        lambda: {
            "status": "RESOLVED_RUNTIME_RETRY",
            "attempts": 1,
        },
    )

    result = repair.run_repair_cycle()
    assert result["status"] == "RESOLVED_RUNTIME_RETRY"
    assert result["classification"] == "TRANSIENT_INFRA"


def test_moved_head_closes_incident_when_failure_already_fixed(
    monkeypatch,
    tmp_path,
):
    incident_path = tmp_path / "incident.json"
    monkeypatch.setattr(repair, "INCIDENT_PATH", incident_path)
    monkeypatch.setattr(
        repair,
        "_main_state",
        lambda: (
            "feature/revenue-intelligence-v2",
            "new-head",
            False,
        ),
    )
    monkeypatch.setattr(
        repair,
        "_verify",
        lambda _root, tests: (True, "1 passed"),
    )

    incident, resolution = repair._reconcile_moved_head({
        "fingerprint": "abc",
        "base_head": "old-head",
        "failing_tests": [
            "tests/test_buyer_discovery.py::test_example"
        ],
    })

    assert incident["base_head"] == "old-head"
    assert resolution is not None
    assert resolution["status"] == "RESOLVED_BY_CONCURRENT_CHANGE"
    assert resolution["verified_tests"] == [
        "tests/test_buyer_discovery.py::test_example"
    ]
    assert not incident_path.exists()


def test_healthy_runtime_closes_stale_env_context_incident(
    monkeypatch,
    tmp_path,
):
    incident = tmp_path / "incident.json"
    state = tmp_path / "state.json"
    latest = tmp_path / "latest.json"
    runtime = tmp_path / "runtime"
    runtime.mkdir()

    incident.write_text(
        """{
          "fingerprint": "env-context",
          "classification": "UNKNOWN",
          "status": "OPEN",
          "log_tail": "RuntimeError:missing required runtime env: SUPABASE_URL"
        }\n"""
    )
    (runtime / "enterprise_contact_intelligence_latest.json").write_text(
        """{
          "error_count": 0,
          "live_outbound_send": false,
          "actual_revenue": false
        }\n"""
    )

    monkeypatch.setattr(repair, "INCIDENT_PATH", incident)
    monkeypatch.setattr(repair, "STATE_PATH", state)
    monkeypatch.setattr(repair, "LATEST_PATH", latest)
    monkeypatch.setattr(repair, "RUNTIME", runtime)

    result = repair.run_repair_cycle()
    assert result["status"] == "RESOLVED_BY_HEALTHY_RUNTIME_STATE"
    assert result["classification"] == "RUNTIME_ENV_CONTEXT"
    saved = repair._load(incident)
    assert saved["status"] == "RESOLVED"
