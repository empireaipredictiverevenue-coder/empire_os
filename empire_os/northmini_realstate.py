#!/usr/bin/env python3
"""North-mini REAL-STATE guard.

TRUTH_AUDIT 2026-07-20 found north-mini emitting plans from a FABRICATED
state slice (LLM cache "4 leads") that never matched the real DB
(4,990 lane_leads / 607 tenants). This module is the SINGLE source of
truth north-mini must read before emitting any plan/campaign.

Every number here is a live DB query. No LLM-derived state. No estimates.
Import this instead of guessing counts.

Usage (north-mini planner):
    from empire_os.northmini_realstate import real_state
    st = real_state()
    # st["tenants"], st["lane_leads"], st["crm_leads"] ...
"""
import sqlite3

DB = "/root/empire_os/empire_os.db"


def real_state() -> dict:
    """Live, real DB state. Never fabricated."""
    c = sqlite3.connect(DB, timeout=20)
    c.row_factory = sqlite3.Row
    try:
        def one(q, d=0):
            try:
                return c.execute(q).fetchone()[0]
            except Exception:
                return d

        tenants = one("SELECT COUNT(*) FROM si_tenant")
        tenants_paid = one(
            "SELECT COUNT(*) FROM si_tenant WHERE crypto_wallet IS NOT NULL")
        lane_leads = one("SELECT COUNT(*) FROM crm_leads")
        buyers = one("SELECT COUNT(*) FROM si_buyer_outreach")
        lanes = one("SELECT COUNT(*) FROM lanes")
        seated = one("SELECT COUNT(*) FROM si_tenant WHERE status='active'")
        invoices_open = one(
            "SELECT COUNT(*) FROM si_ppc_invoices WHERE status='open'")
        settlements_paid = one(
            "SELECT COUNT(*) FROM evaluation_settlements WHERE status='paid'")
        return {
            "tenants": tenants,
            "tenants_with_wallet": tenants_paid,
            "tenants_seated": seated,
            "lane_leads": lane_leads,
            "buyers": buyers,
            "lanes": lanes,
            "invoices_open": invoices_open,
            "settlements_paid": settlements_paid,
            "source": "live_db",
        }
    finally:
        c.close()


if __name__ == "__main__":
    import json
    print(json.dumps(real_state(), indent=2))
