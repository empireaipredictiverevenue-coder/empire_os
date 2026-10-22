"""Identity readiness cannot be manufactured from a service name."""
from __future__ import annotations
import pytest
from scripts import review_existing_research_worker_candidates_20261022 as r


def test_loaded_services_remain_unbound_without_trusted_role():
    snapshots = {
        candidate.unit: {
            "Id": candidate.unit, "LoadState": "loaded",
            "ActiveState": "active", "Type": "oneshot",
            "User": "ubuntu", "Group": "ubuntu",
        }
        for candidate in r.CANDIDATES
    }
    result=r.review(reader=lambda unit:snapshots[unit])
    assert result["status"] == "HOLD_NO_VERIFIED_RESEARCH_MANAGED_IDENTITY"
    assert result["canonical_research_role_defined"] is True
    assert result["production_trusted_signing_enabled"] is False
    assert result["existing_research_role_process_identity_proven"] is False
    assert result["live_research_a2a_reply_verified"] is False
    assert result["production_trusted_research_registration"] is False
    assert len(result["existing_service_candidates"]) == len(r.CANDIDATES)
    assert all(p["managed_research_role_approved"] is False
               for p in result["existing_service_candidates"])
    assert all(p["agent_enrolled"] is False for p in result["existing_service_candidates"])


def test_missing_or_forged_systemd_unit_is_not_a_research_worker():
    result=r.review(reader=lambda _:{"Id":"spoof.service",
                                      "LoadState":"loaded","ActiveState":"active"})
    assert all(p["service_loaded"] is False
               for p in result["existing_service_candidates"])
    assert result["status"]=="HOLD_NO_VERIFIED_RESEARCH_MANAGED_IDENTITY"


def test_unreadable_systemd_metadata_also_holds():
    result=r.review(reader=lambda _: {})
    assert all(p["service_loaded"] is False
               for p in result["existing_service_candidates"])


def test_service_candidates_and_roles_are_pinned_and_not_synthetic():
    names={c.unit for c in r.CANDIDATES}
    assert "empire-coder-worker.service" not in names
    assert "empire-department-cycle.service" in names
    assert "empire-buyer-acquisition-scout.service" in names
    assert "research-agent.service" not in names
    assert all(c.blocker for c in r.CANDIDATES)


def test_reader_rejects_arbitrary_unit():
    with pytest.raises(ValueError, match="only_existing_research_candidate_units"):
        r.fixed_systemd_read("ssh.service")


def test_cli_requires_readonly_and_no_service_starts(monkeypatch,capsys):
    monkeypatch.setattr(r.sys,"argv",["check"])
    assert r.main()==2
    assert "EXACT_READ_ONLY" in capsys.readouterr().out


def test_current_pinned_agent_allowlist_has_no_research_credential():
    from empire_os.agent_runtime_identity_evidence import MANAGED_WORKERS
    assert not [
        worker for worker in MANAGED_WORKERS
        if worker.department=="market_intelligence"
        and worker.role in {"research","deep_research"}
    ]
