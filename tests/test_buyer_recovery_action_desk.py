from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path

import pytest

from empire_os.buyer_recovery_action_desk import (
    RecoveryDeskError, _same_host_evidence, make_packet, plan, save_private,
)


NOW = datetime(2026, 10, 13, 11, tzinfo=timezone.utc)


def _row(name, *, priority=90, attempts=50, reason="no_bound_contact",
         website="https://buyer.example", target_people=None):
    return {
        "status": "deferred",
        "business_name": name,
        "website": website,
        "priority_score": priority,
        "attempts": attempts,
        "reason": reason,
        "offer_key": "predictive_revenue_diagnostic",
        "target_people": target_people if target_people is not None else [
            {"name": "Jane Buyer", "title": "Founder",
             "evidence_url": "https://buyer.example/about?token=private"}
        ],
        "company_contact_routes": [
            {"channel": "webform", "value": "https://buyer.example/contact",
             "verified": True},
            {"channel": "email", "value": "contact@buyer.example",
             "verified": True},
        ],
        "next_retry_at": (NOW - timedelta(minutes=1)).isoformat(),
    }


def test_triage_parked_hot_evidence_and_hold_gates():
    d = {
        "hot": _row("Verified Company"),
        "weak": _row("Retry exhausted", reason="site_timeout",
                     attempts=8, priority=100, target_people=[]),
        "low": _row("Low", priority=40, attempts=0),
        "resolved": {"status": "resolved"},
    }
    r = make_packet(d, source_sha256="a" * 64, now=NOW)
    assert r["counts"]["total"] == 4
    assert r["counts"]["unresolved"] == 3
    assert r["counts"]["parked"] == 2
    assert r["counts"]["due_now"] == 1
    assert r["high_priority_total"] == 2
    assert [p["prospect_id"] for p in r["packets"]] == ["hot", "weak"]
    hot = r["packets"][0]
    assert hot["stage"] == "NAMED_PERSON_EVIDENCE_RECOVERY"
    assert hot["parked_until_new_evidence"] is True
    assert hot["person_evidence_to_reverify"][0]["first_party_url_to_reverify"] == (
        "https://buyer.example/about"
    )
    assert hot["verified_company_route_types"] == ["email", "webform"]
    assert "contact@buyer.example" not in str(r)  # No emails to stdout/snapshot.
    assert hot["first_party_contact_verified"] is False
    assert hot["contact_history_verified"] is False
    assert hot["suppression_verified_for_sending"] is False
    assert hot["outbound_authorized"] is False
    assert r["outbound_sent"] is False and r["db_write"] is False
    assert r["execution_authority"] == "NONE"


def test_only_exact_company_host_and_safe_scheme_yield_person_evidence():
    assert _same_host_evidence("https://www.buyer.example/team?x=secret",
                               "https://buyer.example") == "https://www.buyer.example/team"
    assert _same_host_evidence("https://evilbuyer.example/team",
                               "https://buyer.example") is None
    assert _same_host_evidence("https://buyer.example.evil.test/team",
                               "https://buyer.example") is None
    assert _same_host_evidence("file:///etc/passwd", "https://buyer.example") is None
    assert _same_host_evidence("https://user:pass@buyer.example/about",
                               "https://buyer.example") is None


def test_duplicate_company_domains_are_not_merged_into_single_identity():
    r = make_packet({"p1": _row("One"), "p2": _row("Two")},
                    source_sha256="0" * 64, now=NOW)
    assert r["high_priority_total"] == 2
    assert {p["prospect_id"] for p in r["packets"]} == {"p1", "p2"}
    assert all(p["other_same_domain_records"] == 1 for p in r["packets"])


def test_bounded_packet_keeps_exact_full_high_priority_count():
    d = {f"p{i:02d}": _row(f"Company {i}") for i in range(32)}
    r = make_packet(d, source_sha256="a" * 64, now=NOW)
    assert r["review_packet_count"] == 25
    assert r["review_packet_truncated"] is True
    assert r["high_priority_total"] == 32


def test_empty_queue_never_conjures_buyer_readiness():
    r = make_packet({}, source_sha256="0" * 64, now=NOW)
    assert r["high_priority_total"] == 0
    assert r["packets"] == []
    assert r["counts"]["total"] == 0
    assert r["counts"]["due_now"] == 0
    assert r["counts"]["parked"] == 0
    assert r["counts"]["status_resolved"] == 0
    assert r["outbound_sent"] is False


def test_all_parked_reports_explicit_zero_due():
    p = _row("Parked buyer", reason="no_contact_evidence", attempts=40)
    r = make_packet({"parked": p}, source_sha256="0" * 64, now=NOW)
    assert r["counts"]["due_now"] == 0
    assert r["counts"]["parked"] == 1
    assert r["counts"]["high_priority_eligible"] == 0


def test_source_hash_and_private_write_with_no_queue_mutation(tmp_path):
    queue_dir = tmp_path / "runtime/hunter"
    queue_dir.mkdir(parents=True)
    p = queue_dir / "buyer_deferred_enrichment.json"
    contents = json.dumps({"p1": _row("Company")}) + "\n"
    p.write_text(contents)
    before = sha256(p.read_bytes()).hexdigest()
    r = plan(tmp_path)
    out = save_private(tmp_path, r)
    assert sha256(p.read_bytes()).hexdigest() == before
    assert out.stat().st_mode & 0o777 == 0o600
    assert not out.is_symlink()
    assert json.loads(out.read_text())["source_sha256"] == before
    # Idempotent replacement retains private access.
    save_private(tmp_path, r)
    assert out.stat().st_mode & 0o777 == 0o600


def test_fail_closed_on_source_symlink_and_destination_symlink(tmp_path):
    folder = tmp_path / "runtime/hunter"
    folder.mkdir(parents=True)
    legit = tmp_path / "real.json"
    legit.write_text("{}")
    (folder / "buyer_deferred_enrichment.json").symlink_to(legit)
    with pytest.raises(RecoveryDeskError, match="symlinked"):
        plan(tmp_path)
    (folder / "buyer_deferred_enrichment.json").unlink()
    (folder / "buyer_deferred_enrichment.json").write_text("{}")
    report = plan(tmp_path)
    destination = tmp_path / "runtime/buyer_network_intelligence"
    destination.mkdir()
    (destination / "buyer_recovery_action_desk_latest.json").symlink_to(legit)
    with pytest.raises(RecoveryDeskError, match="destination"):
        save_private(tmp_path, report)
    assert legit.read_text() == "{}"


def test_malformed_queue_fails_closed(tmp_path):
    folder = tmp_path / "runtime/hunter"
    folder.mkdir(parents=True)
    (folder / "buyer_deferred_enrichment.json").write_text('{"p1": 123}')
    with pytest.raises(RecoveryDeskError, match="record"):
        plan(tmp_path)


def test_product_scoped_enterprise_evidence_ranks_above_generic_legal_research():
    generic = _row("Generic legal", priority=100, attempts=25)
    enterprise = _row("Enterprise group", priority=90, attempts=51)
    enterprise["target_product_codes"] = ["predictive_revenue_intelligence_os"]
    packet = make_packet({"legal": generic, "enterprise": enterprise},
                         source_sha256="x" * 64, now=NOW)
    assert [p["prospect_id"] for p in packet["packets"]] == ["enterprise", "legal"]
    assert packet["packets"][0]["product_hypothesis_count"] == 1
    assert packet["packets"][0]["buyer_demand_verified"] is False
