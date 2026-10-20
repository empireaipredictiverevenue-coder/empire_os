import pytest

from empire_os.inbound_provider_contract import (
    InboundNumberRegistry, InboundNumberRoute,
    build_trusted_inbound_status, map_inbound_provider_status,
)
from empire_os.inbound_revenue_recovery import RecoveryLedger
from empire_os.voice_gateway_api import map_vonage_status


def route(*, tenant="business-a", number="+442012345678", enabled=True, owned=True):
    return InboundNumberRoute(
        tenant_id=tenant, e164_number=number, business_name="A Test Company",
        number_ownership_verified=owned, inbound_enabled=enabled,
    )


def call_payload(**overrides):
    base = {
        "to": "+442012345678", "uuid": "vonage-call-1", "event_id": "provider-evt-1",
        "timestamp": "2026-10-20T09:00:00+00:00", "status": "unanswered",
    }
    base.update(overrides)
    return base


def test_inbound_event_must_have_attested_signature():
    registry = InboundNumberRegistry([route()])
    with pytest.raises(ValueError, match="signed_provider"):
        build_trusted_inbound_status(call_payload(), registry=registry)


def test_unregistered_and_disabled_phone_numbers_fail_closed():
    registry = InboundNumberRegistry([route(enabled=False)])
    with pytest.raises(ValueError, match="not_verified_and_enabled"):
        build_trusted_inbound_status(call_payload(), registry=registry,
                                     provider_signature_verified=True)
    registry = InboundNumberRegistry([route()])
    with pytest.raises(ValueError, match="unregistered_inbound"):
        build_trusted_inbound_status(call_payload(to="+441111111111"), registry=registry,
                                     provider_signature_verified=True)


def test_number_ownership_must_be_verified():
    registry = InboundNumberRegistry([route(owned=False)])
    with pytest.raises(ValueError, match="not_verified_and_enabled"):
        build_trusted_inbound_status(call_payload(), registry=registry,
                                     provider_signature_verified=True)


def test_provider_supplied_tenant_does_not_override_owned_number():
    registry = InboundNumberRegistry([route()])
    with pytest.raises(ValueError, match="provider_tenant_mismatch"):
        build_trusted_inbound_status(call_payload(tenant_id="business-b"), registry=registry,
                                     provider_signature_verified=True)


def test_registry_rejects_duplicate_number_assignments():
    with pytest.raises(ValueError, match="duplicate_inbound"):
        InboundNumberRegistry([route(tenant="business-a"), route(tenant="business-b")])


def test_registry_rejects_invalid_phone_number():
    with pytest.raises(ValueError, match="valid_e164"):
        route(number="02012345678")


def test_valid_status_uses_registered_tenant_and_is_idempotent():
    registry = InboundNumberRegistry([route()])
    converted = build_trusted_inbound_status(
        call_payload(), registry=registry, provider_signature_verified=True,
    )
    assert converted.tenant_id == "business-a"
    assert converted.synthetic is False
    assert converted.kind == "unanswered"
    ledger = RecoveryLedger()
    assert ledger.append(converted)
    assert not ledger.append(converted)
    assert ledger.report("business-a")["missed_calls"] == 1
    assert ledger.report("business-b")["missed_calls"] == 0


@pytest.mark.parametrize("provider_status", [
    "started", "ringing", "answered", "unanswered", "timeout",
    "busy", "rejected", "cancelled", "failed", "completed",
])
def test_inbound_status_mapping_matches_existing_voice_lab(provider_status):
    assert "call_" + map_inbound_provider_status(provider_status) == map_vonage_status(provider_status)
