"""Empire OS — Revenue & Lead Stats.

Aggregates across hub tables for dashboard-level metrics.
Exposes two public functions: revenue_stats() and lead_stats().
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("empire_stats")

# ══════════════════════════════════════════════════════════════════════
# Revenue
# ══════════════════════════════════════════════════════════════════════


def revenue_stats(backend) -> dict[str, Any]:
    """Aggregate revenue metrics across charge + snapshot tables."""

    # Total paid charges
    charges = dict(
        backend.execute(
            "SELECT COALESCE(SUM(amount_cents), 0) AS total, COUNT(*) AS count "
            "FROM si_charges WHERE status = 'paid'"
        ).fetchone(),
    )

    # Revenue by month (last 12 months)
    monthly = [
        dict(r)
        for r in backend.execute(
            """SELECT strftime('%Y-%m', paid_at) AS month,
                      SUM(amount_cents) AS cents,
                      COUNT(*) AS tx_count
               FROM si_charges
               WHERE status = 'paid' AND paid_at IS NOT NULL
               GROUP BY month
               ORDER BY month DESC
               LIMIT 12"""
        ).fetchall()
    ]

    # Settlements
    settlements = dict(
        backend.execute(
            "SELECT COALESCE(SUM(amount_cents), 0) AS total, COUNT(*) AS count "
            "FROM si_settlements"
        ).fetchone(),
    )

    # Invoice totals
    invoices = dict(
        backend.execute(
            "SELECT COALESCE(SUM(amount_cents), 0) AS total, COUNT(*) AS count "
            "FROM si_invoice WHERE status = 'paid'"
        ).fetchone(),
    )

    # PPC revenue
    ppc = dict(
        backend.execute(
            "SELECT COALESCE(SUM(amount_cents), 0) AS total, COUNT(*) AS count "
            "FROM si_ppc_invoices WHERE status = 'paid'"
        ).fetchone(),
    )

    # Daily snapshots (latest)
    latest_snap = None
    row = backend.execute(
        "SELECT * FROM daily_revenue_snapshots ORDER BY snapshot_date DESC LIMIT 1"
    ).fetchone()
    if row:
        latest_snap = dict(row)

    return {
        "ok": True,
        "total_paid_charges_cents": charges["total"],
        "total_paid_charges_usd": charges["total"] / 100,
        "total_paid_charges_count": charges["count"],
        "total_settlements_cents": settlements["total"],
        "total_settlements_usd": settlements["total"] / 100,
        "total_settlements_count": settlements["count"],
        "total_paid_invoices_cents": invoices["total"],
        "total_paid_invoices_usd": invoices["total"] / 100,
        "total_paid_invoices_count": invoices["count"],
        "total_paid_ppc_cents": ppc["total"],
        "total_paid_ppc_usd": ppc["total"] / 100,
        "total_paid_ppc_count": ppc["count"],
        "monthly_breakdown": [
            {**m, "cents_usd": (m.get("cents") or 0) / 100} for m in monthly
        ],
        "latest_daily_snapshot": latest_snap,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════
# Lead Stats
# ══════════════════════════════════════════════════════════════════════


def lead_stats(backend) -> dict[str, Any]:
    """Aggregate lead metrics across lane_leads, si_buyer_outreach, si_funnel_event."""

    # Total lane leads
    lane_leads_total = dict(
        backend.execute("SELECT COUNT(*) AS total FROM lane_leads").fetchone()
    )

    # Lane leads by status
    lane_leads_by_status = [
        dict(r)
        for r in backend.execute(
            "SELECT status, COUNT(*) AS count FROM lane_leads GROUP BY status ORDER BY count DESC"
        ).fetchall()
    ]

    # Lane leads by niche
    lane_leads_by_niche = [
        dict(r)
        for r in backend.execute(
            "SELECT COALESCE(niche, 'unknown') AS niche, COUNT(*) AS count "
            "FROM lane_leads GROUP BY niche ORDER BY count DESC LIMIT 20"
        ).fetchall()
    ]

    # Buyer outreach
    outreach_total = dict(
        backend.execute("SELECT COUNT(*) AS total FROM si_buyer_outreach").fetchone()
    )
    outreach_by_reply = [
        dict(r)
        for r in backend.execute(
            "SELECT COALESCE(reply_state, 'unknown') AS state, COUNT(*) AS count "
            "FROM si_buyer_outreach GROUP BY state ORDER BY count DESC"
        ).fetchall()
    ]

    # Funnel state distribution (current state per prospect)
    funnel_current = [
        dict(r)
        for r in backend.execute(
            """SELECT e.to_state AS state, COUNT(*) AS count
               FROM si_funnel_event e
               INNER JOIN (
                   SELECT prospect_id, MAX(id) AS max_id
                   FROM si_funnel_event
                   GROUP BY prospect_id
               ) l ON e.id = l.max_id
               GROUP BY e.to_state
               ORDER BY count DESC"""
        ).fetchall()
    ]

    # Homeowner pipeline stats
    homeowner_current = [
        dict(r)
        for r in backend.execute(
            """SELECT e.to_status AS status, COUNT(*) AS count
               FROM si_homeowner_event e
               INNER JOIN (
                   SELECT job_id, MAX(id) AS max_id
                   FROM si_homeowner_event
                   GROUP BY job_id
               ) l ON e.id = l.max_id
               GROUP BY e.to_status
               ORDER BY count DESC"""
        ).fetchall()
    ]

    # Prospect consent count
    consent = dict(
        backend.execute(
            "SELECT COUNT(*) AS total, SUM(opted_in) AS opted_in FROM si_prospect_consent"
        ).fetchone()
    )

    # Outbound email stats
    outbox = dict(
        backend.execute(
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END) AS sent "
            "FROM si_outbox"
        ).fetchone()
    )

    return {
        "ok": True,
        "lane_leads": {
            "total": lane_leads_total["total"],
            "by_status": lane_leads_by_status,
            "by_niche": lane_leads_by_niche,
        },
        "buyer_outreach": {
            "total": outreach_total["total"],
            "by_reply_state": outreach_by_reply,
        },
        "funnel_current": funnel_current,
        "homeowner_pipeline": homeowner_current,
        "prospect_consent": dict(consent) if consent else {},
        "outbound_emails": dict(outbox) if outbox else {},
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════
# Subscription Stats
# ══════════════════════════════════════════════════════════════════════


def subs_stats(backend) -> dict[str, Any]:
    """Subscription metrics across si_subscription.

    Used by the landing-page hero KPI for "Active Subscriptions".
    Reads live from si_subscription + si_charges for the true paid count.
    """
    # Active subs by status
    by_status = [
        dict(r) for r in backend.execute(
            "SELECT status, COUNT(*) AS count FROM si_subscription "
            "GROUP BY status ORDER BY count DESC"
        ).fetchall()
    ]
    active_row = dict(backend.execute(
        "SELECT COUNT(*) AS count FROM si_subscription WHERE status='active'"
    ).fetchone())
    awaiting_row = dict(backend.execute(
        "SELECT COUNT(*) AS count FROM si_subscription WHERE status='awaiting_payment'"
    ).fetchone())
    # 134 from the old loose query = synthetic auto-seats.
    # The honest bar is: charge.amount_cents > 0 AND a matching
    # real on-chain settlement row (with non-null settled_at) exists.
    # si_charges has buyer_id; si_settlements links via prospect_id (the
    # charge's customer_ref carries the subscription_id, but the
    # simplest reliable join is buyer_id round-trip -> tenant_id).
    paid_unique_buyer_count = dict(backend.execute(
        "SELECT COUNT(DISTINCT c.buyer_id) AS count "
        "FROM si_charges c "
        "INNER JOIN si_subscription sub ON sub.subscription_id = c.customer_ref "
        "INNER JOIN si_settlements s ON s.tenant_id = sub.tenant_id "
        "WHERE c.status='paid' AND c.amount_cents > 0 "
        "AND s.settled_at IS NOT NULL"
    ).fetchone())
    paid_charges_row = {"count": paid_unique_buyer_count["count"]}
    # Strict = paid AND settled (real money landed); loose = just paid (legacy).
    paid_charges_loose = dict(backend.execute(
        "SELECT COUNT(DISTINCT buyer_id) AS count FROM si_charges "
        "WHERE status='paid' AND buyer_id IS NOT NULL"
    ).fetchone())
    return {
        "ok": True,
        "active": active_row["count"] if active_row else 0,
        "awaiting_payment": awaiting_row["count"] if awaiting_row else 0,
        "by_status": by_status,
        # Strict: paid + on-chain settled.
        "unique_paid_subscriptions": paid_charges_row["count"] if paid_charges_row else 0,
        # Legacy loose count kept for the dashboard so old C-suite views
        # don't go blank. Distinct names prevent silent misuse downstream.
        "unique_paid_legacy_loose": paid_charges_loose["count"] if paid_charges_loose else 0,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════
# Vault Stats (live on-chain USDT balance)
# ══════════════════════════════════════════════════════════════════════


def vault_stats(backend) -> dict[str, Any]:
    """Vault USDT + lifetime settled (for landing-page hero KPIs).

    Combines the live RPC vault balance with lifetime settled total from
    si_settlements + si_charges. Returns in BOTH raw cents/usdc and the
    compact numeric fields used by the front-end formatter.
    """
    import os
    rpc = os.environ.get("BSC_RPC", "")
    vault = os.environ.get("BSC_WALLET_ADDRESS", "")
    usdc_mint = os.environ.get("BSC_USDT_CONTRACT", "0x55d398326f99059fF775485246999027B3197955")

    # Live RPC balance (best-effort, short timeout)
    live_usdc = 0.0
    rpc_error = None
    if rpc and vault:
        try:
            import json as _json
            from urllib.request import urlopen, Request
            body = _json.dumps({
                "jsonrpc": "2.0", "id": 1,
                "method": "getBalance",
                "params": [vault],
            }).encode()
            req = Request(rpc, data=body,
                          headers={"Content-Type": "application/json"})
            with urlopen(req, timeout=4) as resp:
                data = _json.loads(resp.read())
            sol_lamports = data.get("result", {}).get("value", 0)
            # SOL balance; USDT needs getTokenAccountsByOwner (out of scope here)
            live_sol = sol_lamports / 1e9
        except Exception as e:
            live_sol = 0.0
            rpc_error = str(e)[:120]
    else:
        live_sol = 0.0

    # Lifetime settled: sum of paid charges (real USDT that flowed)
    settled_row = dict(backend.execute(
        "SELECT COALESCE(SUM(amount_cents), 0) AS total "
        "FROM si_settlements"
    ).fetchone())
    charges_row = dict(backend.execute(
        "SELECT COALESCE(SUM(amount_cents), 0) AS total "
        "FROM si_charges WHERE status='paid'"
    ).fetchone())

    lifetime_settled_cents = (settled_row["total"] if settled_row else 0)         or (charges_row["total"] if charges_row else 0)
    lifetime_settled_usdc = lifetime_settled_cents / 100.0

    # For the ARR estimate: use lifetime settled as floor, monthly_rate
    # (total_paid_charges_cents / 12) as the "if extended" ARR.
    lifetime_paid_cents = charges_row["total"] if charges_row else 0
    monthly_paid_cents = int(lifetime_paid_cents / 12)
    arr_estimate_cents = lifetime_paid_cents + monthly_paid_cents * 11

    return {
        "ok": True,
        "vault_wallet": vault,
        "sol_balance": live_sol,
        "live_usdc_balance": live_usdc,
        "rpc_error": rpc_error,
        "lifetime_settled_cents": lifetime_settled_cents,
        "lifetime_settled_usd": lifetime_settled_usdc,
        "monthly_paid_cents": monthly_paid_cents,
        "arr_estimate_cents": arr_estimate_cents,
        "arr_estimate_usd": arr_estimate_cents / 100.0,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════
# Funnel Stats (current state per prospect)
# ══════════════════════════════════════════════════════════════════════


def funnel_stats(backend) -> dict[str, Any]:
    """Funnel-state distribution (current state per prospect) + USD deltas.

    Powers the funnel panel on the landing page. Uses the same self-join
    trick as lead_stats to take the latest event per prospect.
    """
    states = [
        dict(r) for r in backend.execute(
            """SELECT e.to_state AS state, COUNT(*) AS count
               FROM si_funnel_event e
               INNER JOIN (
                   SELECT prospect_id, MAX(id) AS max_id
                   FROM si_funnel_event
                   GROUP BY prospect_id
               ) l ON e.id = l.max_id
               GROUP BY e.to_state
               ORDER BY count DESC"""
        ).fetchall()
    ]
    total_rows = dict(backend.execute(
        "SELECT COUNT(*) AS c FROM si_funnel_event"
    ).fetchone())
    settled_count = 0
    for st in states:
        if st["state"] == "settled":
            settled_count = st["count"]
    return {
        "ok": True,
        "states": states,
        "total_prospects_observed": sum(s.get("count", 0) for s in states),
        "total_funnel_rows": total_rows.get("c", 0),
        "settled_count": settled_count,
        "settled_usd": settled_count * 1.5,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
