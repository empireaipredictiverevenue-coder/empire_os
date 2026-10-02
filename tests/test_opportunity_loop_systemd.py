from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_opportunity_loop_service_is_least_privilege_observe_runtime():
    text=(ROOT/'deploy/systemd/empire-opportunity-loop.service').read_text()
    assert 'User=ubuntu' in text
    assert 'Group=ubuntu' in text
    assert 'EnvironmentFile=/etc/empire_os.env' in text
    assert 'EnvironmentFile=/etc/empiredb.env' in text
    assert 'scripts/run_opportunity_loop.py' in text
    assert '--min-interval-seconds 900' in text
    assert 'NoNewPrivileges=true' in text
    assert 'ProtectSystem=strict' in text
    assert 'ReadWritePaths=/srv/empire_os/runtime/opportunity_radar /srv/empire_os/runtime/opportunity_factory' in text
    assert 'TimeoutStartSec=10min' in text


def test_opportunity_loop_timer_matches_freshness_guard():
    text=(ROOT/'deploy/systemd/empire-opportunity-loop.timer').read_text()
    assert 'OnUnitInactiveSec=15min' in text
    assert 'Persistent=true' in text
    assert 'Unit=empire-opportunity-loop.service' in text


def test_installer_verifies_no_external_authority():
    text=(ROOT/'scripts/install_opportunity_loop_runtime.sh').read_text()
    assert "assert d.get('execution_authority') == 'none'" in text
    assert "assert d.get('automatic_external_execution_allowed') is False" in text
    assert "assert d.get('outreach_sent') is False" in text
    assert "assert d.get('payment_action') is False" in text
    assert "assert d.get('revenue_recognized') is False" in text
    assert 'astra_duplicate_scheduler=false' in text
