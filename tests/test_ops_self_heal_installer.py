from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_control_plane_installer_installs_privileged_helper_first():
    text = (
        ROOT / "scripts/install_ops_self_heal_control_plane.sh"
    ).read_text()

    helper = text.index(
        'deploy/systemd/empire-ops-privileged-helper.service'
    )
    ops = text.index('deploy/systemd/empire-ops-control.service')
    catalog = text.index(
        'deploy/systemd/empire-commercial-product-catalog.service'
    )

    assert helper < ops < catalog
    assert "systemctl daemon-reload" in text
    assert "systemctl restart empire-ops-privileged-helper.service" in text
    assert "/run/empire-ops/privileged.sock" in text


def test_ops_sentinel_watches_privileged_helper():
    from empire_os.ops_sentinel import CRITICAL_SERVICES, REPAIRABLE_UNITS

    unit = "empire-ops-privileged-helper.service"
    assert unit in CRITICAL_SERVICES
    assert unit in REPAIRABLE_UNITS


def test_control_plane_installer_waits_for_socket_and_diagnoses_failure():
    text = (
        ROOT / "scripts/install_ops_self_heal_control_plane.sh"
    ).read_text()

    assert "for _ in $(seq 1 20)" in text
    assert "test -S /run/empire-ops/privileged.sock" not in text
    assert "[ -S /run/empire-ops/privileged.sock ]" in text
    assert "systemctl status empire-ops-privileged-helper.service" in text
    assert "journalctl -u empire-ops-privileged-helper.service" in text


def test_control_plane_installer_installs_required_timers():
    text = (
        ROOT / "scripts/install_ops_self_heal_control_plane.sh"
    ).read_text()

    assert 'deploy/systemd/empire-ops-control.timer' in text
    assert 'deploy/systemd/empire-commercial-product-catalog.timer' in text
