"""
Tenants — multi-tenant schema for Empire OS SaaS.

Each operator (you, your team, your clients) becomes a Tenant. Each
human seat under a tenant is a Seat. Each seat has a plan tier that
determines which features they can use.

Schema (added to si_funnel_event-compatible SQLite):
  si_tenant         — tenant accounts (one row per operator)
  si_seat           — human seats under a tenant
  si_subscription   — active subscription per tenant
  si_invoice        — billing records
  si_metering       — usage events per tenant per cycle

Pricing tiers (per seat per month):
  free        $0    — 1 seat, 100 cycles/mo
  starter      $99  — 1 seat, 1k cycles/mo
  team        $299  — 5 seats, 10k cycles/mo
  enterprise  $999  — unlimited seats + cycles, custom features
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger("tenants")


# ── Pricing tiers ─────────────────────────────────────────────────

@dataclass
class PlanTier:
    """A subscription plan."""
    name: str
    price_cents_per_seat: int    # monthly
    max_seats: int               # -1 = unlimited
    max_cycles_per_month: int    # -1 = unlimited
    features: list = field(default_factory=list)
    annual_discount_bps: int = 0  # basis points (100 = 1%)
    backend_bps: int = 0          # deal-close backend % (Head 2 hybrid whale)


PLANS = {
    "free": PlanTier(
        name="free", price_cents_per_seat=0,
        max_seats=1, max_cycles_per_month=100,
        features=["core_dashboard", "funnel_view"],
    ),
    "starter": PlanTier(
        name="starter", price_cents_per_seat=9900,
        max_seats=1, max_cycles_per_month=1000,
        features=["core_dashboard", "funnel_view", "agi_workforce"],
        annual_discount_bps=1500,  # 15% off annual
    ),
    "team": PlanTier(
        name="team", price_cents_per_seat=29900,
        max_seats=5, max_cycles_per_month=10000,
        features=["core_dashboard", "agi_workforce", "storm_radar",
                  "satellite_scanner", "lead_filter", "aep_surface"],
        annual_discount_bps=1500,
    ),
    "enterprise": PlanTier(
        name="enterprise", price_cents_per_seat=99900,
        max_seats=-1, max_cycles_per_month=-1,
        features=["*", "white_label", "custom_models", "dedicated_support"],
        annual_discount_bps=2000,
    ),
    "scale": PlanTier(
        name="scale", price_cents_per_seat=990000,   # $9,900/seat/mo
        max_seats=-1, max_cycles_per_month=-1,
        features=["*", "white_label", "custom_models", "dedicated_support",
                  "multi_region", "api_access", "priority_routing"],
        annual_discount_bps=2000,
    ),
    "whale": PlanTier(
        name="whale", price_cents_per_seat=5000000,  # $50,000/seat/mo (blueprint top tier)
        max_seats=-1, max_cycles_per_month=-1,
        features=["*", "white_label", "custom_models", "dedicated_support",
                  "multi_region", "api_access", "priority_routing", "whale_desk",
                  "hybrid_whale_backend", "carrier_drp_roster"],
        annual_discount_bps=2500,
    ),
    "sovereign": PlanTier(
        name="sovereign", price_cents_per_seat=5000000,  # $50,000/mo floor
        max_seats=-1, max_cycles_per_month=-1,
        features=["*", "white_label", "custom_models", "dedicated_support",
                  "multi_region", "api_access", "priority_routing", "whale_desk",
                  "hybrid_whale_backend", "carrier_drp_roster", "sovereign_desk"],
        annual_discount_bps=2500,
        backend_bps=700,   # 7% backend on closed deals (Head 2 hybrid whale)
    ),
}


# ── DB schema ─────────────────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS si_tenant (
    tenant_id        TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    email            TEXT NOT NULL UNIQUE,
    paypal_payer_id  TEXT,
    crypto_wallet    TEXT,
    plan             TEXT NOT NULL DEFAULT 'free',
    billing_cycle    TEXT NOT NULL DEFAULT 'monthly',  -- monthly | annual
    status           TEXT NOT NULL DEFAULT 'active',   -- active | suspended | cancelled
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS si_seat (
    seat_id          TEXT PRIMARY KEY,
    tenant_id        TEXT NOT NULL,
    user_id          TEXT NOT NULL,
    role             TEXT NOT NULL DEFAULT 'operator',  -- owner | operator | viewer
    created_at       TEXT NOT NULL,
    UNIQUE(tenant_id, user_id),
    FOREIGN KEY(tenant_id) REFERENCES si_tenant(tenant_id)
);

CREATE TABLE IF NOT EXISTS si_subscription (
    subscription_id  TEXT PRIMARY KEY,
    tenant_id        TEXT NOT NULL,
    plan             TEXT NOT NULL,
    billing_cycle    TEXT NOT NULL,
    seats            INTEGER NOT NULL DEFAULT 1,
    price_cents      INTEGER NOT NULL,
    status           TEXT NOT NULL DEFAULT 'pending',  -- pending | active | past_due | cancelled
    payment_method   TEXT NOT NULL DEFAULT 'paypal',    -- paypal | crypto_usdc
    payment_ref      TEXT,                              -- paypal_sub_id or tx_hash
    started_at       TEXT NOT NULL,
    current_period_end TEXT NOT NULL,
    created_at       TEXT NOT NULL,
    FOREIGN KEY(tenant_id) REFERENCES si_tenant(tenant_id)
);

CREATE TABLE IF NOT EXISTS si_invoice (
    invoice_id       TEXT PRIMARY KEY,
    tenant_id        TEXT NOT NULL,
    subscription_id  TEXT,
    amount_cents     INTEGER NOT NULL,
    currency         TEXT NOT NULL DEFAULT 'USD',
    status           TEXT NOT NULL DEFAULT 'pending',  -- pending | paid | failed | refunded
    method           TEXT NOT NULL,
    reference        TEXT,
    description      TEXT,
    period_start     TEXT,
    period_end       TEXT,
    created_at       TEXT NOT NULL,
    paid_at          TEXT,
    FOREIGN KEY(tenant_id) REFERENCES si_tenant(tenant_id)
);

CREATE TABLE IF NOT EXISTS si_metering (
    event_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id        TEXT NOT NULL,
    metric           TEXT NOT NULL,    -- "cycles" | "api_calls" | "storage_mb"
    value            INTEGER NOT NULL,
    period           TEXT NOT NULL,    -- YYYY-MM
    created_at       TEXT NOT NULL,
    FOREIGN KEY(tenant_id) REFERENCES si_tenant(tenant_id)
);

CREATE INDEX IF NOT EXISTS idx_metering_tenant_period
    ON si_metering(tenant_id, period, metric);
"""


# ── Models ────────────────────────────────────────────────────────

@dataclass
class Tenant:
    tenant_id: str = ""
    name: str = ""
    email: str = ""
    paypal_payer_id: str = ""
    crypto_wallet: str = ""
    plan: str = "free"
    billing_cycle: str = "monthly"
    status: str = "active"
    created_at: str = ""
    updated_at: str = ""


@dataclass
class Seat:
    seat_id: str = ""
    tenant_id: str = ""
    user_id: str = ""
    role: str = "operator"
    created_at: str = ""


@dataclass
class Subscription:
    subscription_id: str = ""
    tenant_id: str = ""
    plan: str = ""
    billing_cycle: str = "monthly"
    seats: int = 1
    price_cents: int = 0
    status: str = "pending"
    payment_method: str = "paypal"
    payment_ref: str = ""
    started_at: str = ""
    current_period_end: str = ""
    created_at: str = ""


@dataclass
class Invoice:
    invoice_id: str = ""
    tenant_id: str = ""
    subscription_id: str = ""
    amount_cents: int = 0
    currency: str = "USD"
    status: str = "pending"
    method: str = ""
    reference: str = ""
    description: str = ""
    period_start: str = ""
    period_end: str = ""
    created_at: str = ""
    paid_at: str = ""


# ── Store ─────────────────────────────────────────────────────────

class TenantStore:
    """SQLite-backed multi-tenant store."""

    def __init__(self, db_path: str = "/root/empire_os.db"):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA_SQL)
        self._conn.commit()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_tenant(self, name: str, email: str, plan: str = "free") -> Tenant:
        tenant = Tenant(
            tenant_id=str(uuid.uuid4())[:12],
            name=name,
            email=email,
            plan=plan,
            created_at=self._now(),
            updated_at=self._now(),
        )
        self._conn.execute(
            "INSERT INTO si_tenant (tenant_id, name, email, plan, status, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, 'active', ?, ?)",
            (tenant.tenant_id, tenant.name, tenant.email, tenant.plan,
             tenant.created_at, tenant.updated_at),
        )
        self._conn.commit()
        logger.info("tenant created: %s (%s)", tenant.tenant_id, tenant.email)
        return tenant

    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        row = self._conn.execute(
            "SELECT * FROM si_tenant WHERE tenant_id=?", (tenant_id,)
        ).fetchone()
        if not row:
            return None
        return Tenant(**dict(row))

    def get_tenant_by_email(self, email: str) -> Optional[Tenant]:
        row = self._conn.execute(
            "SELECT * FROM si_tenant WHERE email=?", (email,)
        ).fetchone()
        if not row:
            return None
        return Tenant(**dict(row))

    def update_tenant(self, tenant_id: str, **fields):
        fields["updated_at"] = self._now()
        sets = ", ".join(f"{k}=?" for k in fields)
        vals = list(fields.values()) + [tenant_id]
        self._conn.execute(
            f"UPDATE si_tenant SET {sets} WHERE tenant_id=?", vals
        )
        self._conn.commit()

    def add_seat(self, tenant_id: str, user_id: str, role: str = "operator") -> Seat:
        seat = Seat(
            seat_id=str(uuid.uuid4())[:12],
            tenant_id=tenant_id,
            user_id=user_id,
            role=role,
            created_at=self._now(),
        )
        self._conn.execute(
            "INSERT INTO si_seat (seat_id, tenant_id, user_id, role, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (seat.seat_id, seat.tenant_id, seat.user_id, seat.role, seat.created_at),
        )
        self._conn.commit()
        return seat

    def list_seats(self, tenant_id: str) -> list:
        rows = self._conn.execute(
            "SELECT * FROM si_seat WHERE tenant_id=?", (tenant_id,)
        ).fetchall()
        return [Seat(**dict(r)) for r in rows]

    def create_subscription(
        self, tenant_id: str, plan: str, billing_cycle: str = "monthly",
        seats: int = 1, payment_method: str = "paypal",
        payment_ref: str = "",
    ) -> Subscription:
        plan_obj = PLANS.get(plan)
        if not plan_obj:
            raise ValueError(f"unknown plan: {plan}")
        price_per_seat = plan_obj.price_cents_per_seat
        if billing_cycle == "annual":
            price_per_seat = int(
                price_per_seat * 12 * (10000 - plan_obj.annual_discount_bps) / 10000
            )
        total_cents = price_per_seat * seats
        now = datetime.now(timezone.utc)
        period_end = now + timedelta(days=30 if billing_cycle == "monthly" else 365)

        sub = Subscription(
            subscription_id=str(uuid.uuid4())[:12],
            tenant_id=tenant_id,
            plan=plan,
            billing_cycle=billing_cycle,
            seats=seats,
            price_cents=total_cents,
            status="pending",
            payment_method=payment_method,
            payment_ref=payment_ref,
            started_at=now.isoformat(),
            current_period_end=period_end.isoformat(),
        )
        self._conn.execute(
            "INSERT INTO si_subscription (subscription_id, tenant_id, plan, "
            "billing_cycle, seats, price_cents, status, payment_method, "
            "payment_ref, started_at, current_period_end, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (sub.subscription_id, sub.tenant_id, sub.plan, sub.billing_cycle,
             sub.seats, sub.price_cents, sub.status, sub.payment_method,
             sub.payment_ref, sub.started_at, sub.current_period_end,
             self._now()),
        )
        self._conn.commit()
        return sub

    def activate_subscription(self, subscription_id: str, payment_ref: str = ""):
        fields = {"status": "active"}
        if payment_ref:
            fields["payment_ref"] = payment_ref
        sets = ", ".join(f"{k}=?" for k in fields)
        vals = list(fields.values()) + [subscription_id]
        self._conn.execute(
            f"UPDATE si_subscription SET {sets} WHERE subscription_id=?", vals
        )
        self._conn.commit()

    def get_active_subscription(self, tenant_id: str) -> Optional[Subscription]:
        row = self._conn.execute(
            "SELECT * FROM si_subscription WHERE tenant_id=? AND status='active' "
            "ORDER BY started_at DESC LIMIT 1",
            (tenant_id,),
        ).fetchone()
        if not row:
            return None
        return Subscription(**dict(row))

    def create_invoice(
        self, tenant_id: str, amount_cents: int, method: str,
        subscription_id: str = "", reference: str = "",
        description: str = "",
    ) -> Invoice:
        inv = Invoice(
            invoice_id=str(uuid.uuid4())[:12],
            tenant_id=tenant_id,
            subscription_id=subscription_id,
            amount_cents=amount_cents,
            method=method,
            reference=reference,
            description=description,
            created_at=self._now(),
        )
        self._conn.execute(
            "INSERT INTO si_invoice (invoice_id, tenant_id, subscription_id, "
            "amount_cents, currency, status, method, reference, description, "
            "created_at) VALUES (?, ?, ?, ?, 'USD', 'pending', ?, ?, ?, ?)",
            (inv.invoice_id, inv.tenant_id, inv.subscription_id, inv.amount_cents,
             inv.method, inv.reference, inv.description, inv.created_at),
        )
        self._conn.commit()
        return inv

    def mark_invoice_paid(self, invoice_id: str, reference: str = ""):
        fields = {"status": "paid", "paid_at": self._now()}
        if reference:
            fields["reference"] = reference
        sets = ", ".join(f"{k}=?" for k in fields)
        vals = list(fields.values()) + [invoice_id]
        self._conn.execute(
            f"UPDATE si_invoice SET {sets} WHERE invoice_id=?", vals
        )
        self._conn.commit()

    def list_invoices(self, tenant_id: str, limit: int = 50) -> list:
        rows = self._conn.execute(
            "SELECT * FROM si_invoice WHERE tenant_id=? "
            "ORDER BY created_at DESC LIMIT ?",
            (tenant_id, limit),
        ).fetchall()
        return [Invoice(**dict(r)) for r in rows]

    def meter(self, tenant_id: str, metric: str, value: int = 1):
        """Record a usage event for billing/metering."""
        period = datetime.now(timezone.utc).strftime("%Y-%m")
        self._conn.execute(
            "INSERT INTO si_metering (tenant_id, metric, value, period, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (tenant_id, metric, value, period, self._now()),
        )
        self._conn.commit()

    def usage_for_period(self, tenant_id: str, metric: str, period: Optional[str] = None) -> int:
        if not period:
            period = datetime.now(timezone.utc).strftime("%Y-%m")
        row = self._conn.execute(
            "SELECT COALESCE(SUM(value), 0) AS total FROM si_metering "
            "WHERE tenant_id=? AND metric=? AND period=?",
            (tenant_id, metric, period),
        ).fetchone()
        return int(row["total"])


# ── Quota enforcement ────────────────────────────────────────────

def check_quota(store: TenantStore, tenant_id: str, metric: str = "cycles") -> tuple:
    """Check whether a tenant is within their plan quota.

    Returns (allowed: bool, current: int, limit: int, reason: str).
    """
    tenant = store.get_tenant(tenant_id)
    if not tenant:
        return False, 0, 0, "tenant_not_found"
    sub = store.get_active_subscription(tenant_id)
    plan_name = sub.plan if sub else tenant.plan
    plan = PLANS.get(plan_name, PLANS["free"])

    current = store.usage_for_period(tenant_id, metric)
    limit = plan.max_cycles_per_month if metric == "cycles" else -1

    if limit == -1:
        return True, current, limit, "unlimited"

    if current >= limit:
        return False, current, limit, f"quota_exceeded:{plan_name}"

    return True, current, limit, "ok"


def compute_invoice_amount(plan_name: str, seats: int = 1, billing_cycle: str = "monthly") -> int:
    """Compute the invoice amount in cents for a plan/seats/cycle."""
    plan = PLANS.get(plan_name)
    if not plan:
        return 0
    per_seat = plan.price_cents_per_seat
    if billing_cycle == "annual":
        per_seat = int(per_seat * 12 * (10000 - plan.annual_discount_bps) / 10000)
    return per_seat * seats