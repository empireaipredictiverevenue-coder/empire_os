"""Lead Gen pipeline orchestration over existing Empire modules.

Run:  python3 -m empire_os.leadgen.pipeline --phase all
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

# Ensure repo root importable
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from empire_os import sweep_ingest
from empire_os import audit_generator as AG
from empire_os import mail_sender as MS


# ── P1: multi-niche sweep ───────────────────────────────────────────────
def sweep_phase(niches=None, metro="national", limit=50):
    """Ingest a sweep file per niche, tier by fleet, queue outreach leads.

    Expects sweep JSON files at ./sweeps/<niche>.json produced by the
    satellite/market-sweep collector (or any list of company dicts with
    `fleet_size` / `recovery_rate`). Computes the $500/truck/day leak tier
    via sweep_ingest._whale_tier and stores leads.
    """
    niches = niches or ["hvac", "plumbing", "roofing", "solar", "landscaping"]
    swept = 0
    for niche in niches:
        path = os.path.join(_ROOT, "sweeps", f"{niche}.json")
        if not os.path.exists(path):
            print(f"[sweep] skip {niche}: no sweep file at {path}", flush=True)
            continue
        try:
            res = sweep_ingest.ingest(path)
            n = (res or {}).get("total", 0) if isinstance(res, dict) else (res or 0)
            swept += int(n or 0)
            print(f"[sweep] {niche}: ingested {n} leads", flush=True)
        except Exception as e:
            print(f"[sweep] {niche}: ERROR {e!r}", flush=True)
    return {"phase": "sweep", "leads_ingested": swept, "niches": niches}


# ── P2: audit generation (+ private portal) ─────────────────────────────
def audit_phase(limit=50):
    """Generate audits for queued companies; persist + mint portal URLs."""
    try:
        res = AG.run_audit_generation_cycle(limit=limit)
        print(f"[audit] generated {res.get('generated', 0)} audits "
              f"(errors={res.get('errors', 0)})", flush=True)
        return res
    except Exception as e:
        print(f"[audit] ERROR {e!r}", flush=True)
        return {"phase": "audit", "error": str(e)[:200]}


# ── P4: cold email campaign ─────────────────────────────────────────────
def campaign_phase(dry_run=False, limit=25):
    """Send a cold audit-offer email to captured leads via mail_sender.

    Email MUST contain a real pay path (portal URL), per Empire policy —
    no placeholder CTAs. Uses mail_sender._send (Resend/Brevo/MX fallback).

    Schema: leads live in `crm_leads` (email, omega_score, campaign_sent),
    audits in `ai_audit_reports` (company_id, portal_url). We join on
    company_id and only mail leads that have a portal + email + not yet sent.
    """
    sent = 0
    failed = 0
    import sqlite3 as _sql
    c = _sql.connect(AG.DB, timeout=30)
    c.execute("PRAGMA busy_timeout=30000")
    # ensure tracking column exists (idempotent)
    try:
        c.execute("ALTER TABLE crm_leads ADD COLUMN campaign_sent INTEGER DEFAULT 0")
        c.commit()
    except Exception:
        c.rollback()
    rows = c.execute(
        "SELECT l.id, l.business_name, l.email, a.portal_url "
        "FROM crm_leads l JOIN ai_audit_reports a ON l.id = a.company_id "
        "WHERE l.email IS NOT NULL AND l.email != '' "
        "AND (l.campaign_sent IS NULL OR l.campaign_sent = 0) "
        "LIMIT ?", (limit,)
    ).fetchall()
    c.close()
    for company_id, name, email, portal in rows:
        subject = f"Your {name or 'operation'} revenue leak audit is ready"
        body = (
            f"Hi {name or 'there'},\n\n"
            f"We analyzed your operation and found recoverable revenue leaking "
            f"out every single day. Your private audit is here:\n\n"
            f"{portal}\n\n"
            f"No opt-in needed — open it, see the number, decide.\n\n"
            f"— Empire AI\n"
        )
        if dry_run:
            print(f"[campaign] DRY {email}: {subject}", flush=True)
            sent += 1
            c2 = _sql.connect(AG.DB, timeout=30)
            c2.execute("UPDATE crm_leads SET campaign_sent = 1 WHERE id = ?",
                       (company_id,))
            c2.commit()
            c2.close()
            continue
        res = MS._send(email, subject, body)
        ok = bool(res and res.get("ok"))
        sent += 1 if ok else 0
        failed += 0 if ok else 1
        c2 = _sql.connect(AG.DB, timeout=30)
        c2.execute("UPDATE crm_leads SET campaign_sent = 1 WHERE id = ?",
                   (company_id,))
        c2.commit()
        c2.close()
        print(f"[campaign] {'OK' if ok else 'FAIL'} -> {email}", flush=True)
    return {"phase": "campaign", "sent": sent, "failed": failed,
            "targets": len(rows), "dry_run": dry_run}


def run_pipeline(phase="all", niches=None, dry_run=False, limit=50):
    out = {"started": datetime.now(timezone.utc).isoformat()}
    if phase in ("all", "sweep"):
        out["sweep"] = sweep_phase(niches=niches)
    if phase in ("all", "audit"):
        out["audit"] = audit_phase(limit=limit)
    if phase in ("all", "campaign"):
        out["campaign"] = campaign_phase(dry_run=dry_run, limit=limit)
    out["finished"] = datetime.now(timezone.utc).isoformat()
    return out


def main():
    ap = argparse.ArgumentParser(description="Empire Lead Gen pipeline")
    ap.add_argument("--phase", default="all",
                    choices=["all", "sweep", "audit", "campaign"])
    ap.add_argument("--niches", default=None,
                    help="comma list, e.g. hvac,plumbing")
    ap.add_argument("--dry-run", action="store_true",
                    help="campaign: print instead of send")
    ap.add_argument("--limit", type=int, default=50)
    args = ap.parse_args()
    niches = args.niches.split(",") if args.niches else None
    res = run_pipeline(phase=args.phase, niches=niches,
                       dry_run=args.dry_run, limit=args.limit)
    print(json.dumps(res, indent=2, default=str))


if __name__ == "__main__":
    main()
