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


# ── Billing (PayPal + Crypto) ────────────────────────────────────

from empire_os.billing import (
    PayPalConfig, CryptoConfig,
    paypal_create_subscription, paypal_get_subscription,
    paypal_cancel_subscription, crypto_payment_request,
    verify_crypto_payment, BillingEngine,
)


class TestPayPalConfig:
    def test_unconfigured(self, monkeypatch):
        monkeypatch.delenv("PAYPAL_CLIENT_ID", raising=False)
        monkeypatch.delenv("PAYPAL_SECRET", raising=False)
        cfg = PayPalConfig.from_env()
        assert cfg.configured() is False

    def test_configured(self, monkeypatch):
        monkeypatch.setenv("PAYPAL_CLIENT_ID", "client_abc")
        monkeypatch.setenv("PAYPAL_SECRET", "secret_xyz")
        cfg = PayPalConfig.from_env()
        assert cfg.configured() is True
        assert cfg.mode == "sandbox"  # default

    def test_base_url_sandbox_vs_live(self, monkeypatch):
        monkeypatch.setenv("PAYPAL_CLIENT_ID", "x")
        monkeypatch.setenv("PAYPAL_SECRET", "y")
        monkeypatch.setenv("PAYPAL_MODE", "live")
        cfg = PayPalConfig.from_env()
        assert "api-m.paypal.com" in cfg.base_url()


class TestCryptoConfig:
    def test_unconfigured(self, monkeypatch):
        monkeypatch.delenv("VAULT_WALLET_ADDRESS", raising=False)
        cfg = CryptoConfig.from_env()
        assert cfg.configured() is False

    def test_configured(self, monkeypatch):
        monkeypatch.setenv("VAULT_WALLET_ADDRESS", "egJ1t9NZkDs8FvMbfnQTqXzC4KNuhAc9XSfpG9y9AZM")
        cfg = CryptoConfig.from_env()
        assert cfg.configured() is True


class TestCryptoPaymentRequest:
    def test_builds_request(self):
        cfg = CryptoConfig(vault_wallet="vault_addr")
        req = crypto_payment_request(cfg, 10000, "t1", "starter", "monthly")
        assert req["amount_cents"] == 10000
        assert req["amount_usdc"] == 100.0
        assert req["vault_wallet"] == "vault_addr"
        assert "vault_addr" in req["qr_data"]
        assert "empire-os:t1:starter:" in req["memo"] or "t1" in req["memo"]

    def test_qr_includes_memo(self):
        cfg = CryptoConfig(vault_wallet="vault")
        req = crypto_payment_request(cfg, 50000, "tenant42", "team")
        assert "tenant42" in req["qr_data"]
        assert "team" in req["memo"]


class TestBillingEngine:
    def test_available_methods_empty(self, monkeypatch):
        monkeypatch.delenv("PAYPAL_CLIENT_ID", raising=False)
        monkeypatch.delenv("PAYPAL_SECRET", raising=False)
        monkeypatch.delenv("VAULT_WALLET_ADDRESS", raising=False)
        b = BillingEngine()
        assert b.available_methods() == []

    def test_available_methods_crypto(self, monkeypatch):
        monkeypatch.delenv("PAYPAL_CLIENT_ID", raising=False)
        monkeypatch.setenv("VAULT_WALLET_ADDRESS", "vault_abc")
        b = BillingEngine()
        methods = b.available_methods()
        assert any(m["method"] == "crypto_usdc" for m in methods)

    def test_start_subscription_crypto_unconfigured(self, monkeypatch):
        monkeypatch.delenv("VAULT_WALLET_ADDRESS", raising=False)
        b = BillingEngine()
        result = b.start_subscription("t1", "starter", "monthly", 1, "crypto_usdc")
        assert "error" in result


# ── Payout Batch ──────────────────────────────────────────────────

from empire_os.payout_batch import (
    PayoutBatch, PayoutBatchStore, build_payout_batch,
)


class TestPayoutBatch:
    def test_add_request(self):
        b = PayoutBatch(batch_id="abc")
        b.add_request({"amount_cents": 10000, "payout_id": "p1"})
        b.add_request({"amount_cents": 5000, "payout_id": "p2"})
        assert b.total_amount_cents == 15000
        assert len(b.payment_requests) == 2


class TestPayoutBatchStore:
    def test_persists(self, tmp_path):
        path = tmp_path / "batches.json"
        s = PayoutBatchStore(path=path)
        b = PayoutBatch(batch_id="abc", total_amount_cents=1000)
        s.add(b)
        s2 = PayoutBatchStore(path=path)
        assert len(s2.batches) == 1
        assert s2.batches[0]["batch_id"] == "abc"

    def test_update(self, tmp_path):
        s = PayoutBatchStore(path=tmp_path / "batches.json")
        b = PayoutBatch(batch_id="abc")
        s.add(b)
        s.update("abc", status="complete")
        assert s.get("abc")["status"] == "complete"


class TestBuildPayoutBatch:
    def test_builds_deeplinks(self):
        from empire_os.billing import CryptoConfig
        cfg = CryptoConfig(vault_wallet="vault_addr")
        store_sentinel = PayoutBatchStore(path=Path("/tmp/_test_batches.json"))
        payouts = [
            {"payout_id": "p1", "amount_cents": 10000, "status": "pending"},
            {"payout_id": "p2", "amount_cents": 5000, "status": "pending"},
            {"payout_id": "p3", "amount_cents": 9999, "status": "paid"},  # skip
        ]
        batch = build_payout_batch(payouts, cfg, store_sentinel)
        assert len(batch.payment_requests) == 2  # skipped paid
        assert batch.total_amount_cents == 15000
        assert batch.payment_requests[0]["payout_id"] == "p1"
        # Deeplink should reference TokenPocket
        assert "tokenpocket" in batch.payment_requests[0]["deeplink"]


# ── Billing Webhooks ──────────────────────────────────────────────

from empire_os.billing_webhooks import (
    handle_paypal_event, handle_crypto_payment,
    PAYPAL_WEBHOOK_EVENTS,
)


class TestHandlePayPalEvent:
    def test_subscription_created(self, tmp_path):
        s = TenantStore(str(tmp_path / "test.db"))
        t = s.create_tenant("X", "x@x.com")
        event = {
            "event_type": "BILLING.SUBSCRIPTION.CREATED",
            "resource": {"id": "I-ABC123", "custom_id": t.tenant_id},
        }
        result = handle_paypal_event(event, s)
        assert result.handled is True
        assert result.action == "subscription_created"

    def test_unhandled_event(self, tmp_path):
        s = TenantStore(str(tmp_path / "test.db"))
        event = {"event_type": "UNKNOWN.EVENT", "resource": {}}
        result = handle_paypal_event(event, s)
        assert result.handled is False