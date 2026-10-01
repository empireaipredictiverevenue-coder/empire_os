from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_astra_orchestration_installer_preserves_least_privilege_contract():
    text = (
        ROOT / "scripts/install_astra_orchestration_runtime.sh"
    ).read_text(encoding="utf-8")

    assert "systemctl stop" in text
    assert "empire-astra-dispatcher.timer" in text
    assert "empire-department-cycle.timer" in text
    assert "deploy/systemd/empire-astra-dispatcher.service" in text
    assert "deploy/systemd/empire-department-cycle.service" in text
    assert 'chown -R ubuntu:ubuntu "$ROOT/runtime/departments/work"' in text
    assert "systemctl daemon-reload" in text
    assert 'systemctl start "$ASTRA_SERVICE"' in text
    assert 'systemctl start "$DEPT_SERVICE"' in text
    assert 'systemctl restart "$ASTRA_TIMER" "$DEPT_TIMER"' in text
    assert 'systemctl show -p User --value "$ASTRA_SERVICE"' in text
    assert 'systemctl show -p User --value "$DEPT_SERVICE"' in text
    assert "astra_orchestration_runtime=ready" in text

    lower = text.lower()
    assert "send_email" not in lower
    assert "approve_outbound" not in lower
    assert "record_bsc_payment" not in lower
    assert "revenue_recognized=true" not in lower
