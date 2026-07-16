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
        "total_paid_charges_count": charges["count"],
        "total_settlements_cents": settlements["total"],
        "total_settlements_count": settlements["count"],
        "total_paid_invoices_cents": invoices["total"],
        "total_paid_invoices_count": invoices["count"],
        "total_paid_ppc_cents": ppc["total"],
        "total_paid_ppc_count": ppc["count"],
        "monthly_breakdown": monthly,
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
