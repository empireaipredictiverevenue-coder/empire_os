from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from empire_os.astra_executive import refresh_astra_executive
from empire_os.executive_commercial_observer import (
    observe_executive_commercial_roles,
    _status,
)

NOW = datetime(2026, 10, 15, 12, 20, tzinfo=timezone.utc)
SERVICE = {
    "empire-department-cycle.service": {
        "ActiveState": "failed", "Result": "exit-code", "ExecMainStatus": "0",
    },
    "empire-astra-dispatcher.service": {
        "ActiveState": "inactive", "Result": "success", "ExecMainStatus": "0",
        "ExecMainExitTimestamp": "2026-10-15T12:18:00Z",
    },
}


def save(root: Path, rel: str, payload: dict) -> None:
    dest = root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload), encoding="utf-8")


def seed(root: Path, *, stamp: str | None = None) -> None:
    stamp = stamp or NOW.isoformat()
    for filename, schema, controls, final in (
        ("opportunities_runtime_observer_latest.json",
         "empire-opportunities-runtime-observer-v1", ["canonical_identity"], False),
        ("opportunities_final_controls_latest.json",
         "empire-opportunities-final-controls-v1", ["entity_classification"], True),
    ):
        data = {
            "schema_version": schema,
            "lane": "opportunities", "mode": "OBSERVE", "generated_at": stamp,
            "runtime_verified_controls": controls,
            "outbound": False, "payment_execution": False, "db_write": False,
        }
        if final:
            data.update({"entity_classification_proved": True,
                         "outcome_linkage_proved": False})
        else:
            data["status"] = "VERIFIED_RUNTIME"
        save(root, "runtime/opportunities_control/" + filename, data)
    save(root, "runtime/astra/department_cycle_latest.json", {
        "generated_at": NOW.isoformat(), "mode": "OBSERVE",
        "task_monitor": {"attention_count": 281, "notifications_sent": False},
    })
    save(root, "docs/commercial/EXECUTIVE_COMMERCIAL_REVIEW_INPUT_20261015.json", {
        "as_of": NOW.isoformat(),
        "partners": [{
            "name": "AceLeads", "domain": "aceleads.co.uk",
            "market": "UK", "state": "APPLICATION_ACKNOWLEDGED",
            "last_touch_date": "2026-10-13", "contact_history_verified": True,
            "suppressed": False, "paid_revenue_verified": False,
            "evidence_refs": ["gmail_message:1a134b27eca68158"],
        }],
        "operations": {"not_trusted": "historical fixture data"},
    })


def observe(root: Path):
    return observe_executive_commercial_roles(
        root, as_of=NOW, service_evidence=SERVICE,
    )


def test_live_observer_splits_systemd_from_source_proof(tmp_path):
    seed(tmp_path, stamp="2026-10-07T21:16:49Z")
    output = observe(tmp_path)
    assert output["observed_systemd"]["department_cycle"] == "FAILED"
    assert output["observed_systemd"]["astra_dispatcher"] == "SUCCEEDED"
    assert output["opportunity_proof"]["status"] == "STALE"
    assert output["founder_attention"]["count"] == 281
    assert output["review"]["coo"]["opportunities_source_proof_state"] == "STALE"
    assert output["review"]["chief_of_staff"]["top_three_next_actions"][0]["owner"] == "coo"
    bd = output["review"]["business_development"]["partner_cases"]
    assert bd[0]["next_action"] == "OBTAIN_HUMAN_BUYING_BRIEF"
    assert output["outbound_enabled"] is False


def test_observer_does_not_assume_a_current_partner_email(tmp_path):
    seed(tmp_path)
    output = observe(tmp_path)
    assert output["partner_evidence"]["state"] == "HISTORICAL_ONLY"
    assert output["partner_evidence"]["live_provider_mailbox_checked"] is False
    assert output["review_state"] == "HISTORICAL_REVIEW_ONLY"
    assert output["review"]["business_development"]["fresh_verified_uncontacted_count"] == 0


def test_stale_partner_snapshot_does_not_claim_current(tmp_path):
    seed(tmp_path)
    future = observe_executive_commercial_roles(
        tmp_path,
        as_of=NOW + timedelta(days=2),
        service_evidence=SERVICE,
    )
    assert future["partner_evidence"]["state"] == "STALE_REVIEW"
    assert future["review_state"] == "HISTORICAL_REVIEW_ONLY"


def test_invalid_partner_packet_holds_without_crashing_astra(tmp_path):
    seed(tmp_path)
    p = tmp_path / "docs/commercial/EXECUTIVE_COMMERCIAL_REVIEW_INPUT_20261015.json"
    bad = json.loads(p.read_text())
    bad["partners"][0]["contact_history_verified"] = "yes"
    p.write_text(json.dumps(bad))
    result = observe(tmp_path)
    assert result["review_state"] == "INVALID_EVIDENCE_HELD"
    assert result["review"] is None
    assert result["outbound_enabled"] is False


def test_proof_wrong_lane_and_false_authority_fail_closed(tmp_path):
    seed(tmp_path)
    source = tmp_path / "runtime/opportunities_control/opportunities_runtime_observer_latest.json"
    data = json.loads(source.read_text())
    data["lane"] = "other"
    source.write_text(json.dumps(data))
    assert observe(tmp_path)["opportunity_proof"]["status"] == "UNTRUSTED"
    data["lane"] = "opportunities"
    data["outbound"] = True
    source.write_text(json.dumps(data))
    assert observe(tmp_path)["opportunity_proof"]["status"] == "UNTRUSTED"


def test_proof_future_clock_and_symlink_are_rejected(tmp_path):
    seed(tmp_path)
    source = tmp_path / "runtime/opportunities_control/opportunities_runtime_observer_latest.json"
    data = json.loads(source.read_text())
    data["generated_at"] = "2035-01-01T00:00:00Z"
    source.write_text(json.dumps(data))
    assert observe(tmp_path)["opportunity_proof"]["status"] == "UNTRUSTED"
    source.unlink()
    source.symlink_to("/etc/passwd")
    assert observe(tmp_path)["opportunity_proof"]["status"] == "UNTRUSTED"


def test_missing_or_corrupt_proof_visible(tmp_path):
    seed(tmp_path)
    p = tmp_path / "runtime/opportunities_control/opportunities_runtime_observer_latest.json"
    p.unlink()
    assert observe(tmp_path)["opportunity_proof"]["status"] == "MISSING"
    p.write_text("bad-json")
    assert observe(tmp_path)["opportunity_proof"]["status"] == "UNTRUSTED"


def test_unknown_systemd_is_not_healthy():
    assert _status({}) == "UNKNOWN"
    assert _status({"ActiveState": "activating", "Result": "success"}) == "UNKNOWN"
    assert _status({"ActiveState": "failed", "Result": "exit-code"}) == "FAILED"


def test_missing_department_snapshot_does_not_invent_zero_attention(tmp_path):
    seed(tmp_path)
    (tmp_path / "runtime/astra/department_cycle_latest.json").unlink()
    output = observe(tmp_path)
    assert output["founder_attention"]["count"] is None
    assert output["founder_attention"]["count_verified_at_snapshot"] is False
    assert output["review"]["coo"]["founder_notification_evidence"] == "UNKNOWN"


def test_snapshot_observer_is_read_only(tmp_path):
    seed(tmp_path)
    before = {
        p.relative_to(tmp_path): p.read_bytes()
        for p in tmp_path.rglob("*.json") if p.is_file()
    }
    observe(tmp_path)
    after = {
        p.relative_to(tmp_path): p.read_bytes()
        for p in tmp_path.rglob("*.json") if p.is_file()
    }
    assert before == after


def test_integration_rides_existing_astra_refresh_only(tmp_path):
    # Astra already owns the *single* normal snapshot write. The overlay does
    # not own a second timer, mail action, promotion or production controller.
    seed(tmp_path)
    result = refresh_astra_executive(tmp_path)
    attachment = result["executive_commercial_roles"]
    assert attachment["schema_version"] == "empire.executive.commercial_observer.v1"
    assert attachment["execution_authority"] == "none"
    assert attachment["outbound_enabled"] is False
    assert (tmp_path / "runtime/astra/executive_latest.json").is_file()
    assert not (tmp_path / "runtime/executive/partner_review_latest.json").exists()


def test_full_sized_department_snapshot_not_falsely_missing(tmp_path):
    seed(tmp_path)
    path = tmp_path / "runtime/astra/department_cycle_latest.json"
    real_size_like = json.loads(path.read_text())
    real_size_like["oversize_other_departments"] = "x" * 735_000
    path.write_text(json.dumps(real_size_like))
    result = observe(tmp_path)
    assert result["founder_attention"]["count_verified_at_snapshot"] is True
    assert result["founder_attention"]["count"] == 281
    assert result["founder_attention"]["notifications_sent_in_task_monitor"] is False


def test_rejects_unbounded_department_payload(tmp_path):
    seed(tmp_path)
    path = tmp_path / "runtime/astra/department_cycle_latest.json"
    path.write_text(json.dumps({"oversized": "x" * 2_100_000}))
    result = observe(tmp_path)
    assert result["founder_attention"]["count"] is None
    assert result["founder_attention"]["count_verified_at_snapshot"] is False



def test_success_result_is_not_live_success_without_recent_exit():
    assert _status({
        "ActiveState": "inactive", "Result": "success",
        "ExecMainStatus": "0", "ExecMainExitTimestamp": "2026-10-14T12:18:00Z",
    }, now=NOW) == "UNKNOWN"
    assert _status({
        "ActiveState": "inactive", "Result": "success",
        "ExecMainStatus": "0", "ExecMainExitTimestamp": "Thu 2026-10-15 12:18:00 UTC",
    }, now=NOW) == "SUCCEEDED"


def test_missing_partner_source_triggers_business_development_reconciliation(tmp_path):
    seed(tmp_path)
    (tmp_path / "docs/commercial/EXECUTIVE_COMMERCIAL_REVIEW_INPUT_20261015.json").unlink()
    output = observe(tmp_path)
    assert output["partner_evidence"]["state"] == "MISSING"
    tasks = output["review"]["business_development"]["source_tasks"]
    assert [r["action"] for r in tasks] == ["REVALIDATE_CURRENT_PARTNER_EVIDENCE"]
    assert tasks[0]["external_action_authorized"] is False



def test_forged_fresh_file_missing_schema_or_real_controls_is_untrusted(tmp_path):
    seed(tmp_path)
    p = tmp_path / "runtime/opportunities_control/opportunities_runtime_observer_latest.json"
    data = json.loads(p.read_text())
    data["schema_version"] = "untrusted"
    p.write_text(json.dumps(data))
    assert observe(tmp_path)["opportunity_proof"]["status"] == "UNTRUSTED"
    data["schema_version"] = "empire-opportunities-runtime-observer-v1"
    data["runtime_verified_controls"] = []
    p.write_text(json.dumps(data))
    assert observe(tmp_path)["opportunity_proof"]["status"] == "UNTRUSTED"


def test_server_mailbox_read_error_becomes_coo_ownership_not_no_replies(tmp_path):
    seed(tmp_path)
    save(tmp_path, "runtime/conversations_replies_control/founder_mailbox_inprocess_observer_latest.json", {
        "schema_version": "empire-founder-mailbox-inprocess-observer-v1",
        "mode": "OBSERVE",
        "generated_at": NOW.isoformat(),
        "status": "OBSERVER_ERROR", "outbound": False,
        "db_write": False, "mailbox_write": False, "action_authority_granted": False,
        "error_type": "HTTPException",
        "error": "Provider unavailable"
    })
    result = observe(tmp_path)
    assert result["founder_mailbox_observer"]["status"] == "ERROR"
    assert result["review"]["business_development"]["no_new_reply_claim_authorized"] is False
    assert "RESTORE_FOUNDER_MAILBOX_READ_OBSERVABILITY" in {
        r["action"] for r in result["review"]["coo"]["tasks"]
    }
    assert result["outbound_enabled"] is False


def test_mailbox_missing_must_not_be_called_healthy(tmp_path):
    seed(tmp_path)
    result = observe(tmp_path)
    assert result["founder_mailbox_observer"]["status"] == "MISSING"
    assert result["review"]["business_development"]["no_new_reply_claim_authorized"] is False


def test_live_review_cli_is_read_only_and_uses_existing_observer(tmp_path, capsys):
    from scripts.review_executive_commercial_roles import main
    seed(tmp_path)
    rc = main(["--live-observe", "--repo-root", str(tmp_path)])
    output = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert output["schema_version"] == "empire.executive.commercial_observer.v1"
    assert output["founder_mailbox_observer"]["status"] == "MISSING"
    assert output["production_changes"] is False
    assert output["service_restart"] is False
    assert not (tmp_path / "runtime/astra/executive_latest.json").exists()


def test_existing_review_cli_accepts_historical_evidence(tmp_path, capsys):
    from scripts.review_executive_commercial_roles import main
    seed(tmp_path)
    file = Path(__file__).resolve().parents[1] / "docs/commercial/EXECUTIVE_COMMERCIAL_REVIEW_INPUT_20261015.json"
    rc = main(["--input", str(file)])
    output = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert output["chief_of_staff"]["role"] == "chief_of_staff"
    assert output["email_sent"] is False


def test_first_party_loopback_provider_only_is_not_outage_or_buyer_reply(tmp_path):
    seed(tmp_path)
    save(tmp_path, "runtime/conversations_replies_control/founder_mailbox_inprocess_observer_latest.json", {
        "schema_version": "empire-founder-mailbox-inprocess-observer-v1",
        "mode": "OBSERVE",
        "generated_at": NOW.isoformat(),
        "status": "NO_COMPLETE_INBOUND_MESSAGE",
        "mailbox_read_status": "READ_SUCCESS",
        "read_path": "EXISTING_FOUNDER_API_LOOPBACK",
        "provider": "empiredb_canonical_replies",
        "thread_ids": 14,
        "detail_reads": 0,
        "observed": 0,
        "complete_candidates": 0,
        "canonical_reply_identity_verified": False,
        "provider_only_evidence": True,
        "outbound": False,
        "db_write": False,
        "mailbox_write": False,
        "action_authority_granted": False,
    })
    result = observe(tmp_path)
    mailbox = result["founder_mailbox_observer"]
    assert mailbox["status"] == "PROVIDER_ONLY"
    assert mailbox["server_mailbox_provider_read_verified"] is True
    assert mailbox["canonical_reply_identity_verified"] is False
    assert result["review"]["business_development"]["no_new_reply_claim_authorized"] is False
    coo_actions = {row["action"] for row in result["review"]["coo"]["tasks"]}
    assert "VERIFY_CANONICAL_REPLY_IDENTITY_AND_SUPPRESSION" in coo_actions
    assert "RESTORE_FOUNDER_MAILBOX_READ_OBSERVABILITY" not in coo_actions
    assert result["outbound_enabled"] is False


def test_provider_only_requires_exact_failed_identity_contract(tmp_path):
    seed(tmp_path)
    path = tmp_path / "runtime/conversations_replies_control/founder_mailbox_inprocess_observer_latest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    valid = {
        "schema_version": "empire-founder-mailbox-inprocess-observer-v1",
        "mode": "OBSERVE", "generated_at": NOW.isoformat(),
        "status": "NO_COMPLETE_INBOUND_MESSAGE",
        "mailbox_read_status": "READ_SUCCESS",
        "read_path": "EXISTING_FOUNDER_API_LOOPBACK",
        "provider": "empiredb_canonical_replies",
        "thread_ids": 14, "detail_reads": 0,
        "observed": 0, "complete_candidates": 0,
        "canonical_reply_identity_verified": False,
        "provider_only_evidence": True,
        "outbound": False, "db_write": False,
        "mailbox_write": False, "action_authority_granted": False,
    }
    for mutation in (
        {"canonical_reply_identity_verified": True},
        {"observed": 14},
        {"thread_ids": 90000},
        {"read_path": "EXTERNAL_PROVIDER"},
        {"db_write": True},
        {"provider_only_evidence": False},
    ):
        path.write_text(json.dumps({**valid, **mutation}))
        result = observe(tmp_path)
        assert result["founder_mailbox_observer"]["status"] == "ERROR", mutation
        assert result["review"]["business_development"]["no_new_reply_claim_authorized"] is False


def test_selective_human_reply_snapshot_preferred_to_older_hand_off(tmp_path):
    from empire_os.executive_commercial_observer import _partner_packet

    seed(tmp_path)
    latest = tmp_path / "docs/commercial/EXECUTIVE_BD_CURRENT_DISCUSSION_REVIEW_20261015.json"
    latest.write_text(json.dumps({
        "as_of": NOW.isoformat(),
        "partners": [{
            "name": "SolarBriton", "domain": "solarbriton.co.uk",
            "market": "UK", "state": "PILOT_DISCUSSION",
            "last_touch_at": "2026-10-15T10:34:23Z",
            "contact_history_verified": True, "suppressed": False,
            "paid_revenue_verified": False,
            "evidence_refs": ["gmail_message:1a13f20a8e86cf52"],
        }],
    }))
    partners, freshness, source_path = _partner_packet(tmp_path, now=NOW)
    assert freshness == "HISTORICAL_ONLY"
    assert partners[0]["domain"] == "solarbriton.co.uk"
    assert source_path.endswith("EXECUTIVE_BD_CURRENT_DISCUSSION_REVIEW_20261015.json")
    result = observe(tmp_path)
    actions = result["review"]["chief_of_staff"]["top_three_next_actions"]
    assert any(a.get("partner") == "SolarBriton" for a in actions)
    assert all(a["external_action_authorized"] is False for a in actions)


def test_expired_manual_reply_snapshot_triggers_source_review_instead_of_sending(tmp_path):
    from empire_os.executive_commercial_observer import _partner_packet

    seed(tmp_path)
    latest = tmp_path / "docs/commercial/EXECUTIVE_BD_CURRENT_DISCUSSION_REVIEW_20261015.json"
    latest.write_text(json.dumps({
        "as_of": "2026-10-13T10:00:00Z", "partners": [],
    }))
    partners, freshness, source_path = _partner_packet(tmp_path, now=NOW)
    assert freshness == "STALE_REVIEW"
    assert source_path.endswith("EXECUTIVE_BD_CURRENT_DISCUSSION_REVIEW_20261015.json")
    result = observe(tmp_path)
    assert result["partner_evidence"]["state"] == "STALE_REVIEW"
    assert result["review"]["business_development"]["source_tasks"][0]["action"] == (
        "REVALIDATE_CURRENT_PARTNER_EVIDENCE"
    )
    assert result["outbound_enabled"] is False
