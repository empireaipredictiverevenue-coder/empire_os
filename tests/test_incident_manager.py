from empire_os.incident_manager import build_incident_report, correlate_findings


def test_business_blocker_is_observed_not_auto_executed():
    report = build_incident_report({
        "findings": [{
            "code": "commercial_loop_blocked",
            "severity": "info",
            "component": "commercial_loop",
            "repairable": False,
            "commercial_priority": 95,
        }]
    })
    item = report["diagnoses"][0]
    assert item["label"] == "business_blocker"
    assert item["playbook"] == "observe_business_blocker"
    assert item["execution_authority"] == "none"
    assert report["controls_execution"] is False


def test_unknown_failure_escalates_without_commands():
    report = build_incident_report({
        "findings": [{
            "code": "novel_failure",
            "severity": "warning",
            "component": "mystery",
            "repairable": False,
            "commercial_priority": 80,
        }]
    })
    item = report["diagnoses"][0]
    assert item["label"] == "unknown"
    assert item["playbook"] == "escalate"
    assert item["escalation_required"] is True
    assert report["raw_command_generation"] is False


def test_repairable_findings_are_left_to_healer():
    assert correlate_findings([{
        "code": "critical_service_down",
        "severity": "critical",
        "component": "empire-public-gateway.service",
        "repairable": True,
        "commercial_priority": 100,
    }]) == []


def test_source_evidence_gap_is_observed_without_escalation():
    report = build_incident_report({
        "findings": [{
            "code": "source_ingest_evidence_unverified",
            "severity": "info",
            "component": "source_health",
            "repairable": False,
            "commercial_priority": 65,
        }]
    })
    item = report["diagnoses"][0]
    assert item["label"] == "data_freshness"
    assert item["playbook"] == "observe_data_evidence"
    assert item["escalation_required"] is False
