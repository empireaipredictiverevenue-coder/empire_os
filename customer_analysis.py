#!/usr/bin/env python3
"""Empire OS — evidence-only customer analysis.

Reads observed CRM fields and returns them without synthetic intent,
habit, trigger, or discovery inference. Missing evidence remains unknown.
The `use_agi` argument is retained for API compatibility but no LLM
inference is used to manufacture customer attributes.
"""

import json
import subprocess
import sys
import time

CONTAINER = "empire-hub"
OUT = "/root/feedback/customer_analysis.json"


def _crm(query, args=()):
    cmd = [
        "incus", "exec", CONTAINER, "--", "/root/venv/bin/python3",
        "/root/empire_os/crm_query.py", query, json.dumps(list(args)),
    ]
    try:
        return json.loads(
            subprocess.run(
                cmd, capture_output=True, text=True, timeout=20
            ).stdout
        )
    except Exception:
        return []


def analyze(customer=None, vertical=None, limit=20, use_agi=True):
    """Return observed CRM evidence only; unknown fields stay unknown."""
    if customer:
        rows = _crm(
            "SELECT business_name, email, source, url FROM si_buyer_outreach "
            "WHERE business_name LIKE ? LIMIT ?",
            (f"%{customer}%", limit),
        )
    else:
        v = vertical or "logistics"
        rows = _crm(
            "SELECT business_name, email, source, url FROM si_buyer_outreach "
            "WHERE source LIKE ? ORDER BY prospect_id DESC LIMIT ?",
            (f"%{v}%", limit),
        )

    customers = []
    for r in rows:
        if not isinstance(r, list) or len(r) < 3:
            continue
        biz = r[0]
        email = r[1]
        src = r[2]
        url = r[3] if len(r) > 3 else ""
        customers.append({
            "customer": biz,
            "email": email,
            "source": src,
            "url": url,
            "vertical": src.split(":")[-1] if src else (vertical or ""),
            "reachable": bool(email),
            "triggers": [f"observed_source:{src}"] if src else [],
            "intent": None,
            "habit_loop": None,
            "discovery_path": src or None,
            "analysis_basis": "observed_crm_fields_only",
        })

    return {
        "analyzed": len(customers),
        "agi_used": False,
        "customers": customers,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


if __name__ == "__main__":
    cust = sys.argv[1] if len(sys.argv) > 1 else None
    vert = sys.argv[2] if len(sys.argv) > 2 else "logistics"
    print(json.dumps(analyze(customer=cust, vertical=vert), indent=2)[:700])
