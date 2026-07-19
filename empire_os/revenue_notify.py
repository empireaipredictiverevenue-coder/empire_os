#!/usr/bin/env python3
"""revenue_notify — money-only Telegram alerts.
Only revenue events call this: invoice PAID, lead BILLED, affiliate commission,
subscription invoice. Ops/noise (restarts, digests, funnel state) must NOT.
When TELEGRAM_MONEY_ONLY=1, the gateway drops any non-revenue message anyway;
this helper always tags revenue=True so money events always get through.
"""
import sys
sys.path.insert(0, "/root/empire_os")
import empire_os.hermes_gateway as g


def _send(icon: str, msg: str) -> dict:
    try:
        return g._telegram_send(f"{icon} <b>MONEY</b> {msg}", revenue=True)
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}


def paid(invoice_id: str, usd: float, buyer: str = "") -> dict:
    return _send("✅", f"PAID {invoice_id[:8]} ${usd:,.2f}"
                 + (f" — {buyer}" if buyer else ""))


def billed(invoice_id: str, usd: float, niche: str = "") -> dict:
    return _send("🧾", f"BILLED {invoice_id[:8]} ${usd:,.2f}"
                 + (f" — {niche}" if niche else ""))


def commission(affiliate_id: str, usd: float, lead_id: str = "") -> dict:
    return _send("🤝", f"AFFILIATE ${usd:,.2f} to {affiliate_id[:8]}"
                 + (f" (lead {lead_id})" if lead_id else ""))


def subscription(tenant: str, usd: float, tier: str = "") -> dict:
    return _send("📅", f"MRR {tenant} ${usd:,.2f}/mo"
                 + (f" [{tier}]" if tier else ""))


def loop_stall(msg: str) -> dict:
    """Money-loop health alert (loop_closure_watchdog)."""
    return _send("🚨", f"LOOP STALL {msg}")
