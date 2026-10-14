"""Gmail evidence has first priority in existing scout; never auto-sends."""
from pathlib import Path
import subprocess
from types import SimpleNamespace

from scripts import run_buyer_acquisition_scout as scout


def receipt(status="PASS", code=0):
    return {
        "status": status, "exit_code": code,
        "mode": "OBSERVE", "outbound_sent": False,
        "execution_authority": "NONE",
    }


def test_reviewed_gmail_cycle_runs_before_web_discovery_with_no_outbound(tmp_path):
    calls = []
    def invoke(args, **options):
        calls.append((args, options))
        return SimpleNamespace(returncode=0, stdout='{"status":"PASS"}', stderr="")
    result = scout.refresh_known_partner_gmail_before_public_search(
        str(tmp_path), runner=invoke
    )
    assert result == receipt()
    assert len(calls) == 1
    args, opts = calls[0]
    assert args[1:] == ["-m", "scripts.run_buyer_gmail_evidence_cycle"]
    assert opts["timeout"] <= 60
    assert opts["env"]["EMPIRE_MODE"] == "OBSERVE"
    assert opts["env"]["EMPIRE_EXECUTION_AUTHORITY"] == "OBSERVE"
    assert opts["env"]["OUTBOUND_ENABLED"] == "0"
    assert opts["env"]["EMPIRE_OUTBOUND_ENABLED"] == "0"
    assert opts["env"]["LIVE_OUTBOUND"] == "0"
    assert opts["cwd"] == tmp_path.resolve()


def test_gmail_presearch_failure_does_not_grant_outbound(tmp_path):
    result = scout.refresh_known_partner_gmail_before_public_search(
        str(tmp_path),
        runner=lambda *_a, **_kw: SimpleNamespace(returncode=2)
    )
    assert result == receipt("BLOCKED", 2)


def test_gmail_presearch_timeout_fails_closed(tmp_path):
    def blocked(*a, **kw):
        raise subprocess.TimeoutExpired("gmail-only", 60)
    assert scout.refresh_known_partner_gmail_before_public_search(
        str(tmp_path), runner=blocked
    ) == receipt("TIMEOUT", 124)


def test_mailbox_preflight_not_repeated_after_research(tmp_path):
    calls = []
    def runner(args, **opts):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    result = scout.research_network_after_scout(
        str(tmp_path), runner=runner,
        mailbox_preflight=receipt("PASS", 0)
    )
    assert result["status"] == "PASS"
    assert result["relationship_registry"] == "PASS"
    assert result["mailbox_ingest_in_this_cycle"] is True
    assert result["outbound_sent"] is False
    assert len(calls) == 1
    assert calls[0][1].endswith("run_buyer_network_evidence_cycle.py")


def test_gmail_failure_preserves_other_research_work(tmp_path):
    calls = []
    def runner(args, **opts):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    result = scout.research_network_after_scout(
        str(tmp_path), runner=runner,
        mailbox_preflight=receipt("TIMEOUT", 124)
    )
    assert result["status"] == "PARTIAL"
    assert result["buyer_network_research"] == "PASS"
    assert result["relationship_registry"] == "TIMEOUT"
    assert result["mailbox_ingest_in_this_cycle"] is False
    assert len(calls) == 1


def test_unsafe_claim_of_mailbox_preflight_cannot_mark_registry_pass(tmp_path):
    calls = []
    def runner(args, **opts):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    result = scout.research_network_after_scout(
        str(tmp_path), runner=runner,
        mailbox_preflight={
            "status": "PASS", "outbound_sent": True,
            "execution_authority": "NONE", "mode": "OBSERVE"
        },
    )
    assert result["status"] == "PARTIAL"
    assert result["relationship_registry"] == "BLOCKED"
    assert result["mailbox_ingest_in_this_cycle"] is False
    assert len(calls) == 1


def test_program_order_mailbox_before_slow_public_query(tmp_path):
    source = (Path(scout.__file__)).read_text()
    main = source.split("def main() -> int:", 1)[1]
    gmail_position = main.index("refresh_known_partner_gmail_before_public_search(")
    public_position = main.index("public_research = refresh_public_research_seeds(")
    scout_position = main.index("payload = refresh_buyer_scout(")
    after_position = main.index("research_network_after_scout(")
    assert gmail_position < public_position < scout_position < after_position
    assert "mailbox_preflight=mailbox_preflight" in main


def test_does_not_create_additional_timer_or_service_file():
    source = (Path(scout.__file__)).read_text()
    assert "systemctl start" not in source
    assert "enable --now" not in source
    assert "scripts.run_buyer_gmail_evidence_cycle" in source


def test_slow_research_timeout_does_not_erase_successful_prior_gmail(tmp_path):
    def timeout_public_query(args, **options):
        raise subprocess.TimeoutExpired(args, 300)

    prior = scout.refresh_known_partner_gmail_before_public_search(
        str(tmp_path),
        runner=lambda *_a, **_kw: SimpleNamespace(returncode=0)
    )
    result = scout.research_network_after_scout(
        str(tmp_path), runner=timeout_public_query,
        mailbox_preflight=prior
    )
    assert prior["status"] == "PASS"
    assert result["status"] == "PARTIAL"
    assert result["buyer_network_research"] == "TIMEOUT"
    assert result["relationship_registry"] == "PASS"
    assert result["mailbox_ingest_in_this_cycle"] is True
    assert result["outbound_sent"] is False
    assert result["execution_authority"] == "NONE"
