import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_legacy_permit_recovery_runner_is_observe_only():
    text = (
        ROOT / "scripts/run_legacy_permit_recovery_observer.py"
    ).read_text()

    assert "refresh_legacy_permit_recovery_observer" in text
    assert "database_write_performed" in text
    assert "canonical_promotion_performed" in text
    assert "outbound_sent" in text
    assert "actual_revenue" in text
    assert "execution_authority" in text
    assert "update_cumulative_inventory" in text
    assert "cumulative_unique_inventory" in text
    assert "cumulative_project_only" in text


def test_legacy_permit_recovery_core_has_no_mutating_rest_method():
    path = ROOT / "empire_os/legacy_permit_recovery.py"
    text = path.read_text()
    tree = ast.parse(text)

    methods = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name):
            continue
        if node.func.id != "request_json":
            continue
        if not node.args:
            continue
        method = node.args[0]
        if isinstance(method, ast.Constant) and isinstance(method.value, str):
            methods.append(method.value.upper())

    assert methods
    assert set(methods) == {"GET"}
    assert '"NO_PROMOTION_OBSERVE_ONLY"' in text
    assert '"historical_only": True' in text
    assert '"current_truth": False' in text
