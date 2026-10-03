from datetime import datetime, timezone

from empire_os.outbound_evidence_chain import GENESIS
from empire_os.outbound_ringleader_runtime import persist_evidence_and_decision


class MemoryReader:
    def __init__(self, head=None):
        self.head = head

    def latest_evidence_head(self):
        return self.head


class MemoryWriter:
    def __init__(self):
        self.observations = []
        self.decisions = []

    def append_observation(self, row):
        self.observations.append(dict(row))
        return {"id": f"o{len(self.observations)}"}

    def append_decision(self, row):
        self.decisions.append(dict(row))
        return {"id": f"d{len(self.decisions)}"}


def context():
    return {
        "deliverability": {"health": "GREEN"},
        "provider_policy_permits_use_case": True,
        "authentication": {
            "spf_aligned": True,
            "dkim_aligned": True,
            "dmarc_valid": True,
            "tls_ready": True,
        },
        "recipient_quality": {"verified": True},
        "placement": {"measured": True},
        "domain_sovereignty": {
            "domain": "mail.example.com",
            "purpose": "relationship",
            "registrar_account_owned": True,
            "dns_authority_owned": True,
            "mfa_enabled": True,
            "domain_lock_enabled": True,
            "auto_renew_enabled": True,
            "dns_zone_exported": True,
            "dmarc_rua_empire_owned": True,
            "provider_portable_sender_identity": True,
            "recovery_path_verified": True,
        },
    }


def test_runtime_persists_metric_specific_hash_chain_then_decision():
    reader = MemoryReader()
    writer = MemoryWriter()

    result = persist_evidence_and_decision(
        scope_key="tenant-a",
        source="resend",
        provider_payload={
            "domain": "mail.example.com",
            "sent": 10,
            "delivered": 10,
            "bounced": 0,
        },
        ringleader_context=context(),
        reader=reader,
        writer=writer,
        observed_at=datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc),
    )

    assert len(writer.observations) == 3
    hashes = [row["evidence_hash"] for row in writer.observations]
    assert len(set(hashes)) == 3
    assert writer.observations[0]["previous_evidence_hash"] == GENESIS
    assert writer.observations[1]["previous_evidence_hash"] == hashes[0]
    assert writer.decisions[0]["previous_evidence_hash"] == hashes[-1]
    assert writer.decisions[0]["mutation_authorized"] is False
    assert result["mutation_authorized"] is False


def test_runtime_continues_existing_passport_head():
    existing = "a" * 64
    reader = MemoryReader(existing)
    writer = MemoryWriter()

    persist_evidence_and_decision(
        scope_key="tenant-a",
        source="auth_observer",
        provider_payload={
            "domain": "mail.example.com",
            "spf_aligned": True,
        },
        ringleader_context=context(),
        reader=reader,
        writer=writer,
        observed_at=datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc),
    )

    assert writer.observations[0]["previous_evidence_hash"] == existing
