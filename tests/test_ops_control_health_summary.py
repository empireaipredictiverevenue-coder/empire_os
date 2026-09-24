from scripts import run_ops_control_cycle as ops_control


def test_ops_control_source_exposes_structured_health_domains():
    source = (
        __import__("pathlib").Path(
            "scripts/run_ops_control_cycle.py"
        ).read_text()
    )

    assert '"health_domains": health_domains' in source
    assert '"blocking_findings": blocking_findings' in source
    assert '"blocking_finding_count": len(blocking_findings)' in source
    assert '"infrastructure"' in source
    assert '"services_and_timers"' in source
    assert '"acquisition_and_buyer_pipeline"' in source
    assert '"model_providers"' in source
