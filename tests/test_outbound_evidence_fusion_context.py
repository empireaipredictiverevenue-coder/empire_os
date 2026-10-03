from datetime import datetime, timezone

from empire_os.outbound_deliverability_ringleader import evaluate_ringleader
from empire_os.outbound_evidence_fusion import (
    build_ringleader_context_from_fusion,
    fuse_evidence,
)


NOW = datetime(2026, 10, 3, 19, 0, tzinfo=timezone.utc)


def row(signal, value, source="sensor", confidence=1.0):
    return {
        "signal": signal,
        "value": value,
        "source": source,
        "observed_at": NOW.isoformat(),
        "confidence": confidence,
    }


def complete_rows():
    rows = [
        row("deliverability_health", "GREEN"),
        row("provider_policy_permitted", True),
        row("spf_aligned", True),
        row("dkim_aligned", True),
        row("dmarc_valid", True),
        row("tls_ready", True),
        row("domain", "outbound.example.com"),
        row("domain_purpose", "prospecting"),
    ]
    for signal in (
        "registrar_account_owned",
        "dns_authority_owned",
        "mfa_enabled",
        "domain_lock_enabled",
        "auto_renew_enabled",
        "dns_zone_exported",
        "dmarc_rua_empire_owned",
        "provider_portable_sender_identity",
        "recovery_path_verified",
    ):
        rows.append(row(signal, True))
    return rows


def test_complete_consensus_builds_current_fleet_context():
    fused = fuse_evidence(complete_rows(), now=NOW)
    projected = build_ringleader_context_from_fusion(fused)

    assert projected["evidence_posture"] == "CURRENT"
    assert projected["gaps"] == []
    decision = evaluate_ringleader(projected["context"])
    assert decision["posture"] == "READY"
    assert decision["mutation_authorized"] is False


def test_conflicted_auth_signal_never_enters_ringleader_as_trusted():
    rows = complete_rows()
    rows.append(row("dkim_aligned", False, source="second-sensor"))
    fused = fuse_evidence(rows, now=NOW)
    projected = build_ringleader_context_from_fusion(fused)

    assert projected["evidence_posture"] == "CONFLICT"
    assert "dkim_aligned" in projected["critical_conflicts"]
    assert "dkim_aligned" not in projected["context"]["authentication"]

    decision = evaluate_ringleader(projected["context"])
    assert decision["posture"] == "REMEDIATE"


def test_low_confidence_policy_evidence_prevents_ready():
    rows = complete_rows()
    rows = [
        item
        for item in rows
        if item["signal"] != "provider_policy_permitted"
    ]
    rows.append(row("provider_policy_permitted", True, confidence=0.4))

    fused = fuse_evidence(rows, now=NOW)
    projected = build_ringleader_context_from_fusion(fused)
    decision = evaluate_ringleader(projected["context"])

    assert "provider_policy_permitted" in projected["gaps"]
    assert decision["posture"] == "LIMITED"
