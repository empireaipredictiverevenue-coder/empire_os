from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_linkedin_revenue_department_service_is_observe_only():
    text = (
        ROOT
        / "deploy/systemd/empire-linkedin-revenue-department.service"
    ).read_text()

    assert "build_linkedin_revenue_department.py" in text
    assert "ReadWritePaths=/srv/empire_os/runtime" in text
    assert "ProtectSystem=strict" in text
    assert "NoNewPrivileges=true" in text
    assert "outbound" not in text.lower()
    assert "linkedin.com" not in text.lower()


def test_linkedin_revenue_department_timer_is_bounded():
    text = (
        ROOT
        / "deploy/systemd/empire-linkedin-revenue-department.timer"
    ).read_text()

    assert "OnUnitInactiveSec=30min" in text
    assert "Persistent=true" in text
    assert "Unit=empire-linkedin-revenue-department.service" in text


def test_service_orders_after_buyer_scout_without_mutating_it():
    text = (
        ROOT
        / "deploy/systemd/empire-linkedin-revenue-department.service"
    ).read_text()

    assert "After=network-online.target empire-buyer-acquisition-scout.service" in text
    assert "run_buyer_acquisition_scout.py" not in text
    assert "persist_buyer_scout_candidates.py" not in text
