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
