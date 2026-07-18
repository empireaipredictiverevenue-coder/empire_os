#!/usr/bin/env python3
"""
VERTICAL DATA FEEDS — sellable MCP module + firehose supply.

Exposes the 29k real leads-derived signals (permits, jobs, business triggers,
intent) as a machine-readable firehose agents can pull per vertical.

Source of truth: container CRM DB (empire-hub) queried via crm_query.py.
No external deps — stdlib only (subprocess to incus, json). KISS/DRY.

Used by:
  - mcp_lead_server.py `vertical_feed` tool (call_tool handler imports this)
  - direct:  from vertical_feed import feed; feed('logistics', 5)
"""
import json
import re
import subprocess

CONTAINER = "empire-hub"
CRM_QUERY = "/root/empire_os/crm_query.py"
DB_PROC = ["incus", "exec", CONTAINER, "--",
           "/root/venv/bin/python3", CRM_QUERY]

# vertical catalog (mirror of mcp_lead_server.VERTICALS)
VERTICALS = ["logistics", "warehouse", "roofing", "hvac", "dental", "realestate",
             "law", "marketing", "agency", "plumbing", "solar", "medspa",
             "staffing", "saas", "finance", "insurance", "construction",
             "trucking", "freight", "manufacturing"]

DOM_RE = re.compile(r"https?://([A-Za-z0-9.-]+\.[A-Za-z]{2,})")


def _container_query(sql, args=()):
    """Run a SELECT against the container CRM DB via crm_query.py."""
    cmd = DB_PROC + [sql, json.dumps(list(args))]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout
        return json.loads(out) if out.strip() else []
    except Exception as e:
        return [{"error": str(e)[:120]}]


def _domain(url, email):
    """Best-effort domain from url, else email domain."""
    if url:
        m = DOM_RE.search(url)
        if m:
            return m.group(1)
    if email and "@" in email:
        return email.rsplit("@", 1)[1]
    return ""


def feed(vertical, limit=10):
    """Pull real signal rows for a vertical from the container CRM DB.

    Returns machine-readable signal rows:
        {company, domain, trigger, source, date}
    `trigger` = the signal source class (serper / host_hunter / parallel /
    serpapi / empire_leads ...) — the business-trigger/intent event.
    `date`    = first_touch_at (when the signal was captured).

    Falls back to a niche match if no source-prefixed rows exist for the
    vertical (broadens the firehose without empty results).
    """
    vertical = (vertical or "").lower()
    v = vertical
    # primary: source encodes vertical as '<prefix>:<vertical>'
    rows = _container_query(
        "SELECT business_name, email, url, source, first_touch_at "
        "FROM si_buyer_outreach WHERE source LIKE ? "
        "ORDER BY first_touch_at DESC LIMIT ?",
        (f"%:{v}%", limit))
    if not rows or (isinstance(rows[0], dict) and "error" in rows[0]):
        # fallback: match on niche taxonomy
        rows = _container_query(
            "SELECT business_name, email, url, source, first_touch_at "
            "FROM si_buyer_outreach WHERE niche LIKE ? "
            "ORDER BY first_touch_at DESC LIMIT ?",
            (f"%{v}%", limit))
    signals = []
    for r in rows:
        if not isinstance(r, list) or len(r) < 5:
            continue
        business_name, email, url, source, date = r[0], r[1], r[2], r[3], r[4]
        trigger = source.split(":", 1)[0] if source and ":" in source else (source or "")
        signals.append({
            "company": business_name or "",
            "domain": _domain(url, email),
            "trigger": trigger,
            "source": source or "",
            "date": (date or "")[:10],
        })
    return {"count": len(signals), "vertical": vertical, "signals": signals,
            "provenance": "29k+ real leads-derived signals (TS-2)",
            "settlement": "USDC MRR via Empire Vault (no Stripe)"}


if __name__ == "__main__":
    import sys
    v = sys.argv[1] if len(sys.argv) > 1 else "logistics"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    print(json.dumps(feed(v, n), indent=2))
