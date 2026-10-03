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



def test_observer_consumes_current_open_source_bundle_as_fleet_evidence():
    result = observe_once(
        FakeProvider(),
        scope_key="tenant-a",
        context=fleet_context(),
        evidence_bundle={
            "status": "CURRENT",
            "warnings": [],
            "sources": {
                "checkdmarc": {
                    "domain": "mail.example.com",
                    "spf": {"valid": True, "record": "v=spf1 -all"},
                    "dmarc": {"valid": False, "error": "invalid record"},
                },
            },
            "mutation_authorized": False,
        },
        now=datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc),
    )
    assert result["evidence_bundle"]["status"] == "CURRENT"
    assert result["ringleader"]["posture"] == "HOLD"
    assert "open_source_evidence_hold" in result["ringleader"]["hard_holds"]


def test_stale_bundle_is_reported_but_not_projected():
    result = observe_once(
        FakeProvider(),
        scope_key="tenant-a",
        context=fleet_context(),
        evidence_bundle={
            "status": "STALE",
            "warnings": ["evidence_bundle_stale"],
            "sources": {
                "checkdmarc": {
                    "domain": "mail.example.com",
                    "dmarc": {"valid": False},
                },
            },
            "mutation_authorized": False,
        },
        now=datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc),
    )
    assert result["evidence_bundle"]["status"] == "STALE"
    assert result["ringleader"]["open_source_health"] is None
    assert result["ringleader"]["posture"] == "READY"



def estate_inventory(*, include_orphan_capacity=False):
    transports = [{
        "id": "t1",
        "transport_key": "transport:a",
        "state": "ACTIVE",
        "policy_compatible": True,
    }]
    domains = [{
        "id": "d1",
        "domain": "mail.example.com",
        "lifecycle_state": "ACTIVE",
    }]
    mailboxes = [{
        "id": "m1",
        "mailbox_key": "sender:1",
        "email_address": "sender@mail.example.com",
        "domain_id": "d1",
        "transport_id": "t1",
        "state": "ACTIVE",
        "reputation_credit": 50,
    }]
    pools = [{
        "id": "p1",
        "pool_key": "mailbox:primary",
        "pool_kind": "MAILBOX",
        "state": "ACTIVE",
    }]
    pool_members = [{
        "pool_id": "p1",
        "member_type": "MAILBOX",
        "member_key": "sender:1",
        "active": True,
    }]
    capacity_events = [{
        "id": "c1",
        "mailbox_key": "sender:1",
        "domain": "mail.example.com",
        "transport_key": "transport:a",
        "event_type": "SET_LIMIT",
        "capacity_limit": 20,
        "units": 0,
        "recorded_at": "2026-10-03T08:00:00+00:00",
    }]
    if include_orphan_capacity:
        capacity_events.append({
            "id": "c2",
            "mailbox_key": "sender:missing",
            "domain": "mail.example.com",
            "event_type": "SET_LIMIT",
            "capacity_limit": 5,
            "units": 0,
            "recorded_at": "2026-10-03T09:00:00+00:00",
        })

    return {
        "transports": transports,
        "domains": domains,
        "mailboxes": mailboxes,
        "pools": pools,
        "pool_members": pool_members,
        "capacity_events": capacity_events,
        "seed_mailboxes": [{
            "seed_key": "seed:gmail:1",
            "active": True,
            "ownership_verified": True,
        }],
    }


def test_observer_reports_converged_sender_estate_without_authorizing_send():
    result = observe_once(
        FakeProvider(),
        scope_key="tenant-a",
        context=fleet_context(),
        estate_inventory=estate_inventory(),
        now=datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc),
    )
    assert result["sender_estate_reconciliation"]["status"] == "CONVERGED"
    assert result["ringleader"]["sender_estate_reconciliation"]["status"] == "CONVERGED"
    assert result["ringleader"]["posture"] == "READY"
    assert result["mutation_authorized"] is False


def test_observer_propagates_sender_estate_integrity_failure_to_hold():
    result = observe_once(
        FakeProvider(),
        scope_key="tenant-a",
        context=fleet_context(),
        estate_inventory=estate_inventory(include_orphan_capacity=True),
        now=datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc),
    )
    assert result["sender_estate_reconciliation"]["status"] == "HOLD"
    assert result["ringleader"]["posture"] == "HOLD"
    assert "sender_estate_reconciliation_hold" in result["ringleader"]["hard_holds"]



def test_observer_marks_expired_capacity_lease_for_reconciliation_not_auto_release():
    inventory = estate_inventory()
    inventory["capacity_events"].append({
        "id": "c-expired",
        "mailbox_key": "sender:1",
        "domain": "mail.example.com",
        "transport_key": "transport:a",
        "event_type": "RESERVE",
        "units": 4,
        "capacity_limit": None,
        "reservation_key": "res:expired",
        "idempotency_key": "idem:expired:reserve",
        "lease_expires_at": "2026-10-03T11:00:00+00:00",
        "recorded_at": "2026-10-03T10:00:00+00:00",
    })
    result = observe_once(
        FakeProvider(),
        scope_key="tenant-a",
        context=fleet_context(),
        estate_inventory=inventory,
        now=datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc),
    )
    reconciliation = result["sender_estate_reconciliation"]
    assert reconciliation["status"] == "DEGRADED"
    assert "capacity_reservation_recovery_required" in reconciliation["warnings"]
    assert result["ringleader"]["posture"] == "REMEDIATE"
    assert any(
        task["action"] == "RECONCILE_ESTATE"
        for task in result["ringleader"]["tasks"]
    )
    assert reconciliation["capacity_reservations"]["recovery_actions"][0][
        "mutation_authorized"
    ] is False



def test_observer_emits_provider_metrics_heartbeat_when_telemetry_policy_enabled():
    ctx = fleet_context()
    ctx["telemetry_policy"] = {
        "required_sources": ["provider_metrics"],
        "critical_sources": ["provider_metrics"],
        "default_max_age_minutes": 30,
    }
    result = observe_once(
        FakeProvider(),
        scope_key="tenant-a",
        context=ctx,
        now=datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc),
    )
    telemetry = result["telemetry_context"]
    assert telemetry is not None
    assert telemetry["required_sources"] == ["provider_metrics"]
    assert telemetry["heartbeats"][0]["source"] == "provider_metrics"
    assert result["ringleader"]["telemetry_sla"]["posture"] == "CURRENT"
    assert result["mutation_authorized"] is False


def test_observer_blocks_scale_when_required_event_ingest_heartbeat_missing():
    ctx = fleet_context()
    ctx["telemetry_policy"] = {
        "required_sources": [
            "provider_metrics",
            "provider_event_ingest",
        ],
        "critical_sources": [
            "provider_metrics",
            "provider_event_ingest",
        ],
        "default_max_age_minutes": 30,
    }
    result = observe_once(
        FakeProvider(),
        scope_key="tenant-a",
        context=ctx,
        now=datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc),
    )
    assert result["ringleader"]["posture"] == "LIMITED"
    assert result["ringleader"]["telemetry_sla"]["posture"] == "BLIND"
    assert result["ringleader"]["hard_holds"] == []
    assert any(
        task["action"] == "BLOCK_SCALE"
        and task["reason"] == "telemetry_critical_blind"
        for task in result["ringleader"]["tasks"]
    )


def test_observer_accepts_current_external_event_ingest_heartbeat():
    ctx = fleet_context()
    ctx["telemetry_policy"] = {
        "required_sources": [
            "provider_metrics",
            "provider_event_ingest",
        ],
        "critical_sources": [
            "provider_metrics",
            "provider_event_ingest",
        ],
        "default_max_age_minutes": 30,
    }
    ctx["telemetry_heartbeats"] = [{
        "source": "provider_event_ingest",
        "observed_at": "2026-10-03T11:55:00+00:00",
        "success": True,
        "coverage": True,
        "details": {"consumer": "resend_webhook"},
    }]
    result = observe_once(
        FakeProvider(),
        scope_key="tenant-a",
        context=ctx,
        now=datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc),
    )
    assert result["ringleader"]["telemetry_sla"]["posture"] == "CURRENT"
    assert not any(
        task["action"] == "BLOCK_SCALE"
        for task in result["ringleader"]["tasks"]
    )
    assert result["ringleader"]["mutation_authorized"] is False


def test_observer_reports_stale_external_event_ingest_heartbeat():
    ctx = fleet_context()
    ctx["telemetry_policy"] = {
        "required_sources": [
            "provider_metrics",
            "provider_event_ingest",
        ],
        "critical_sources": [
            "provider_metrics",
            "provider_event_ingest",
        ],
        "default_max_age_minutes": 30,
    }
    ctx["telemetry_heartbeats"] = [{
        "source": "provider_event_ingest",
        "observed_at": "2026-10-03T10:00:00+00:00",
        "success": True,
        "coverage": True,
    }]
    result = observe_once(
        FakeProvider(),
        scope_key="tenant-a",
        context=ctx,
        now=datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc),
    )
    assert result["ringleader"]["telemetry_sla"]["posture"] == "STALE"
    assert any(
        task["action"] == "REFRESH_EVIDENCE"
        and task["reason"] == "telemetry_critical_stale"
        for task in result["ringleader"]["tasks"]
    )



def test_observer_can_probe_local_provider_event_ingest_health():
    calls = []

    def probe(source, url, *, now):
        calls.append((source, url, now))
        return {
            "source": source,
            "observed_at": now.isoformat(),
            "success": True,
            "coverage": True,
            "details": {
                "provider": "resend",
                "signature_verification_configured": True,
            },
        }

    ctx = fleet_context()
    ctx["telemetry_policy"] = {
        "required_sources": [
            "provider_metrics",
            "provider_event_ingest",
        ],
        "critical_sources": [
            "provider_metrics",
            "provider_event_ingest",
        ],
    }
    result = observe_once(
        FakeProvider(),
        scope_key="tenant-a",
        context=ctx,
        telemetry_probe=probe,
        now=datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc),
    )

    assert calls[0][0] == "provider_event_ingest"
    assert calls[0][1] == "http://127.0.0.1:8097/health"
    assert result["ringleader"]["telemetry_sla"]["posture"] == "CURRENT"
    assert not any(
        task["action"] == "BLOCK_SCALE"
        for task in result["ringleader"]["tasks"]
    )
