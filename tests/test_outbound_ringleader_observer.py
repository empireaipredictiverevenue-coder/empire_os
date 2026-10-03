from datetime import datetime, timezone

import pytest

from empire_os.outbound_ringleader_observer import observe_once


class FakeProvider:
    def __init__(self):
        self.calls = []

    def metrics(self, *, start, end, granularity="daily"):
        self.calls.append((start, end, granularity))
        return {
            "data": [{
                "domain_name": "mail.example.com",
                "sent": 100,
                "delivered": 100,
                "bounced": 0,
                "complained": 0,
            }]
        }


class MemoryReader:
    def latest_evidence_head(self):
        return None


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


def fleet_context():
    return {
        "provider_policy_permits_use_case": True,
        "authentication": {
            "spf_aligned": True,
            "dkim_aligned": True,
            "dmarc_valid": True,
            "tls_ready": True,
        },
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


def test_observer_uses_one_three_window_provider_pull_and_never_mutates():
    provider = FakeProvider()
    result = observe_once(
        provider,
        scope_key="tenant-a",
        context=fleet_context(),
        now=datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc),
    )
    assert len(provider.calls) == 3
    assert result["mode"] == "OBSERVE"
    assert result["ringleader"]["evaluation_scope"] == "FLEET"
    assert result["mutation_authorized"] is False
    assert result["persistence"]["configured"] is False


def test_observer_persists_raw_1d_evidence_and_one_decision_when_bound():
    provider = FakeProvider()
    writer = MemoryWriter()

    result = observe_once(
        provider,
        scope_key="tenant-a",
        context=fleet_context(),
        reader=MemoryReader(),
        writer=writer,
        now=datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc),
    )

    assert len(writer.observations) == 4
    assert len(writer.decisions) == 1
    assert writer.decisions[0]["mutation_authorized"] is False
    assert result["persistence"]["observations"] == 4


def test_observer_fails_closed_on_half_configured_persistence():
    with pytest.raises(RuntimeError, match="configured_together"):
        observe_once(
            FakeProvider(),
            scope_key="tenant-a",
            context=fleet_context(),
            reader=MemoryReader(),
            writer=None,
        )
