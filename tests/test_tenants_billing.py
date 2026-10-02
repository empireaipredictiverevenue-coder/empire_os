"""Tests for tenants, billing, payout batch, and webhook handlers."""
import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ── Tenants ────────────────────────────────────────────────────────

from empire_os.tenants import (
    TenantStore, PlanTier, PLANS,
    compute_invoice_amount, check_quota,
)


class TestPlanTiers:
    def test_free_plan(self):
        p = PLANS["free"]
        assert p.price_cents_per_seat == 0
        assert p.max_seats == 1

    def test_starter_plan(self):
        p = PLANS["starter"]
        assert p.price_cents_per_seat == 9900  # $99
        assert p.annual_discount_bps == 1500  # 15%

    def test_team_plan(self):
        p = PLANS["team"]
        assert p.price_cents_per_seat == 29900  # $299

    def test_enterprise_unlimited(self):
        p = PLANS["enterprise"]
        assert p.max_seats == -1
        assert p.max_cycles_per_month == -1


class TestComputeInvoice:
    def test_monthly(self):
        assert compute_invoice_amount("starter", seats=1, billing_cycle="monthly") == 9900

    def test_annual_with_discount(self):
        annual = compute_invoice_amount("starter", seats=1, billing_cycle="annual")
        # 9900 * 12 * 0.85 = 100,980
        assert annual == 100980

    def test_multiple_seats(self):
        total = compute_invoice_amount("team", seats=5, billing_cycle="monthly")
        assert total == 149500  # $299 * 5

    def test_free_plan(self):
        assert compute_invoice_amount("free") == 0


class TestTenantStore:
    def test_create_tenant(self, tmp_path, monkeypatch):
        db = str(tmp_path / "test.db")
        s = TenantStore(db)
        t = s.create_tenant("Acme Corp", "ops@acme.com", plan="team")
        assert t.tenant_id != ""
        assert t.email == "ops@acme.com"
        assert t.plan == "team"

    def test_get_tenant_by_email(self, tmp_path):
        db = str(tmp_path / "test.db")
        s = TenantStore(db)
        s.create_tenant("Acme", "ops@acme.com")
        t = s.get_tenant_by_email("ops@acme.com")
        assert t is not None
        assert t.name == "Acme"

    def test_get_unknown_email_returns_none(self, tmp_path):
        s = TenantStore(str(tmp_path / "test.db"))
        assert s.get_tenant_by_email("nobody@example.com") is None

    def test_seats(self, tmp_path):
        s = TenantStore(str(tmp_path / "test.db"))
        t = s.create_tenant("Acme", "ops@acme.com")
        s.add_seat(t.tenant_id, "user1@acme.com", role="operator")
        s.add_seat(t.tenant_id, "user2@acme.com", role="operator")
        seats = s.list_seats(t.tenant_id)
        assert len(seats) == 2

    def test_subscription_lifecycle(self, tmp_path):
        s = TenantStore(str(tmp_path / "test.db"))
        t = s.create_tenant("Acme", "ops@acme.com")
        sub = s.create_subscription(
            t.tenant_id, plan="starter", billing_cycle="monthly",
            seats=1, payment_method="paypal",
        )
        assert sub.status == "pending"
        s.activate_subscription(sub.subscription_id, payment_ref="paypal_xyz")
        active = s.get_active_subscription(t.tenant_id)
        assert active is not None
        assert active.status == "active"
        assert active.payment_ref == "paypal_xyz"

    def test_invoice_paid(self, tmp_path):
        s = TenantStore(str(tmp_path / "test.db"))
        t = s.create_tenant("Acme", "ops@acme.com")
        inv = s.create_invoice(t.tenant_id, amount_cents=9900, method="paypal")
        s.mark_invoice_paid(inv.invoice_id, reference="PAY-123")
        invs = s.list_invoices(t.tenant_id)
        assert invs[0].status == "paid"
        assert invs[0].reference == "PAY-123"

    def test_metering(self, tmp_path):
        s = TenantStore(str(tmp_path / "test.db"))
        t = s.create_tenant("Acme", "ops@acme.com")
        s.meter(t.tenant_id, "cycles", 5)
        s.meter(t.tenant_id, "cycles", 3)
        assert s.usage_for_period(t.tenant_id, "cycles") == 8


class TestCheckQuota:
    def test_free_plan_under_limit(self, tmp_path):
        s = TenantStore(str(tmp_path / "test.db"))
        t = s.create_tenant("X", "x@x.com", plan="free")
        allowed, current, limit, reason = check_quota(s, t.tenant_id)
        assert reason == "ok"
        assert limit == 100

    def test_enterprise_unlimited(self, tmp_path):
        s = TenantStore(str(tmp_path / "test.db"))
        t = s.create_tenant("X", "x@x.com", plan="enterprise")
        allowed, current, limit, reason = check_quota(s, t.tenant_id)
        assert reason == "unlimited"

# ── Legacy billing retirement / canonical USDT-BSC rail ──────────

import pytest
from empire_os import billing, billing_webhooks, payout_batch
from empire_os.payment_rail_policy import RetiredPaymentRailError


def test_legacy_billing_surface_is_retired():
    state = billing.status()
    assert state["status"] == "RETIRED"
    assert state["asset"] == "USDT"
    assert state["network"] == "BSC"
    assert state["chain_id"] == 56


def test_legacy_payment_execution_fails_closed():
    with pytest.raises(RetiredPaymentRailError):
        billing.crypto_payment_request()
    with pytest.raises(RetiredPaymentRailError):
        billing_webhooks.handle_crypto_payment({})
    with pytest.raises(RetiredPaymentRailError):
        payout_batch.build_payout_batch([])


def test_billing_engine_only_advertises_canonical_rail():
    assert billing.BillingEngine().available_methods() == [
        {"method": "usdt_bsc", "chain_id": 56}
    ]
