#!/usr/bin/env python3
"""
Empire OS - outreach-now runner.

Generates 50 prospect leads from our lane_leads database that the
founder can paste into a CRM/email tool. Uses copywriting-agent
to render the email body for each prospect via /v1/copy (POST).

Output:
  - /root/empire_os/outreach_pack/prospects_YYYY-MM-DD.csv
  - /root/empire_os/outreach_pack/prospects_YYYY-MM-DD.md  (paste-ready)
  - /root/empire_os/outreach_pack/emails_YYYY-MM-DD.md    (per-prospect copy)

Usage:  python3 /root/empire_os/scripts/outreach_now.py [--limit 50]
"""
import argparse, csv, json, os, sqlite3, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

DB  = os.environ.get("HUB_DB_PATH",
                   "/root/empire_os/empire_os.db")
     # If on host and DB doesn't exist, will be picked up via
     # /v1/leads/sample endpoint on hub.
HUB = os.environ.get("HUB_URL", "http://10.118.155.218:8081")
OUT = Path("/root/empire_os/outreach_pack"); OUT.mkdir(parents=True, exist_ok=True)


def fetch_prospects(db_path: str, limit: int) -> list:
    cnx = sqlite3.connect(db_path)
    try:
        rows = []
        for niche, n in [("general_contractor", max(1, limit // 2)),
                         ("plumbing", max(1, limit // 3)),
                         ("hvac", max(1, limit // 8)),
                         ("roofing", max(1, limit // 8))]:
            sql = (
                "SELECT id, niche, metro, name, phone, email, "
                "state, source, created_at FROM lane_leads "
                "WHERE niche = ? AND (phone IS NOT NULL AND phone != '') "
                "ORDER BY created_at DESC LIMIT ?"
            )
            for r in cnx.execute(sql, (niche, n)):
                rows.append({
                    "id": r[0], "niche": r[1], "metro": r[2],
                    "name": r[3], "phone": r[4], "email": r[5],
                    "state": r[6], "source": r[7],
                    "first_seen_at": r[8],
                })
                if len(rows) >= limit:
                    break
            if len(rows) >= limit:
                break
        return rows[:limit]
    finally:
        cnx.close()


def copy_via_hub(brief: dict) -> str:
    """Call /v1/copy to get a copywriting-agent draft.

    Returns the body text. Falls back to a static template if agent
    unavailable.
    """
    fallback = (
        f"Hey {{name}},\n\n"
        f"this is the Empire OS team. We noticed a recent {{niche}} in {{metro}}. "
        f"Empire OS delivers exclusive leads (one agency per (niche × metro), "
        f"no recycled leads, real-time webhook, USDC on Solana) for agencies "
        f"with 50+ active projects in your metro. Want a 1-day free trial of "
        f"the pipeline?\n\nFirst 14 days are free — cancel anytime.\n\nEmpire OS\n"
    )
    try:
        body = json.dumps({
            "kind": "email_outreach",
            "niche": brief.get("niche", ""),
            "metro": brief.get("metro", ""),
            "name":  brief.get("name",  ""),
            "audience": "agency_founder_50M_revenue",
            "tier":   brief.get("tier", "silver"),
            "subject_template": "Empire OS for {{metro}} {{niche}}",
        }).encode()
        req = urllib.request.Request(f"{HUB}/v1/copy",
                                     data=body,
                                     headers={"Content-Type": "application/json"},
                                     method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        body_text = data.get("body") or data.get("copy") or data.get("text") or ""
        return body_text or fallback.format(**brief)
    except Exception as e:
        return fallback.format(**brief)


def write_csv(rows: list, path: Path):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "niche", "metro",
                                           "name", "phone", "email",
                                           "state", "source",
                                           "first_seen_at", "email_body"])
        w.writeheader()
        for r in rows:
            w.writerow(r)


def write_md(rows: list, path: Path):
    lines = ["# Empire OS Outreach Pack\n",
             f"_Generated {datetime.now(timezone.utc).isoformat()}_\n",
             f"_Total prospects: {len(rows)}_\n\n"]
    lines.append("| # | Niche | Metro | Name | Phone | Email | Source | First Seen |")
    lines.append("|---|-------|-------|------|-------|-------|--------|------------|")
    for i, r in enumerate(rows, 1):
        lines.append(
            f"| {i} | {r['niche']} | {r['metro']} | {str(r['name'])[:30]} | "
            f"{r['phone']} | {r['email']} | {r['source']} | {r['first_seen_at']} |"
        )
    path.write_text("\n".join(lines))


def write_emails(rows: list, path: Path):
    """One email per prospect, copy from copywriting-agent."""
    body = ["# Empire OS Outreach Email Body", "\n",
            f"_Generated {datetime.now(timezone.utc).isoformat()}_\n\n"]
    for i, r in enumerate(rows, 1):
        brief = {"niche": r["niche"],
                 "metro": r["metro"],
                 "name":  (r.get("name") or "there").strip() or "there"}
        body.append(f"## #{i} - {r['niche']} in {r['metro']} - {r['phone']}")
        body.append("\n**Subject options:**\n")
        body.append(f"- Empire OS for {r['metro']} {r['niche']}: real leads, USDC billing\n")
        body.append(f"- Exclusive {r['niche']} leads in {r['metro']} - one agency per lane\n")
        body.append(f"- Pay-in-USDC lead-gen for {r['metro']} agencies\n")
        body.append("\n**Body:**\n")
        body.append(copy_via_hub(brief))
        body.append("\n---\n")
    path.write_text("\n".join(body))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=50)
    args = ap.parse_args()

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"[{datetime.now(timezone.utc).isoformat()}] outreach-now starting - {args.limit}")
    rows = fetch_prospects(DB, args.limit)
    if not rows:
        print("[WARN] no prospects found with phone. aborting.")
        sys.exit(0)
    csv_path = OUT / f"prospects_{today}.csv"
    md_path  = OUT / f"prospects_{today}.md"
    em_path  = OUT / f"emails_{today}.md"
    write_csv(rows, csv_path)
    write_md(rows, md_path)
    print(f"[OK] {len(rows)} prospects to {csv_path}")
    print(f"[OK] markdown -> {md_path}")
    print(f"[OK] drafting emails via copywriting-agent...")
    write_emails(rows, em_path)
    print(f"[OK] emails -> {em_path}")
    print()
    print("First 5 prospects:")
    for r in rows[:5]:
        print(f"  {r['niche']:25} {r['metro']:6} {r['phone']:20} {str(r['name'])[:30]}")


if __name__ == "__main__":
    main()
