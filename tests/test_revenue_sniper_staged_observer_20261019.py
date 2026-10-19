"""Offline service contract for a staged observer, never a scanner daemon."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_staged_observer_uses_no_network_and_no_mutation():
    unit = (ROOT / "deploy/systemd/empire-revenue-sniper-observer.service").read_text()
    assert "User=ubuntu" in unit
    assert "Type=oneshot" in unit
    assert "ProtectSystem=strict" in unit
    assert "ProtectHome=read-only" in unit
    assert "NoNewPrivileges=true" in unit
    assert "RestrictAddressFamilies=AF_UNIX" in unit
    assert "IPAddressDeny=any" in unit
    assert "--read-only" in unit
    assert "scripts.review_revenue_sniper_dispatch_readiness_20261019" in unit
    assert "--scout /srv/empire_os/runtime/buyer_acquisition/scout_latest.json" in unit
    assert "--review /srv/empire_os/runtime/buyer_acquisition/review_readiness_latest.json" in unit
    assert "--exchange /srv/empire_os/runtime/commercial_exchange/latest.json" in unit
    forbidden = (
        "ExecStartPost=", "ExecStopPost=", "WorkingDirectory=/srv/empire_os",
        "EnvironmentFile=", "ReadWritePaths=", "curl ", "psql ",
        "run_buyer_acquisition_scout", "lead_sniper_agent",
        "outbox", "send_email", "ingest_candidate",
    )
    # Comment text is non-executable; test service directives for calls.
    exec_lines = [
        line for line in unit.splitlines()
        if line.startswith("ExecStart=") or line.startswith("ExecStartPre=")
    ]
    assert len(exec_lines) == 1
    assert not any(term in exec_lines[0] for term in forbidden)


def test_timer_is_staged_review_not_new_crawler():
    path = ROOT / "deploy/systemd/empire-revenue-sniper-observer.timer"
    unit = path.read_text()
    assert "OnCalendar=*:0/30" in unit
    assert "Persistent=false" in unit
    assert "Unit=empire-revenue-sniper-observer.service" in unit
    assert "buyer-acquisition-scout.service" not in unit
    assert "lead-sniper-agent" not in unit
