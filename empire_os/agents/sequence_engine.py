#!/usr/bin/env python3
"""
Empire OS — Sequence Engine
Manages email sequences with A/B testing, VSL, newsletter, upsell.
"""
import sqlite3
import argparse
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

DB = "/root/empire_os/empire_os.db"
TEMPLATE_DIR = Path("/root/empire_os/email_templates")

def get_template(name):
    """Load HTML template or return None."""
    path = TEMPLATE_DIR / name
    if path.exists():
        return path.read_text()
    return None

def now():
    return datetime.now(timezone.utc).isoformat()

def get_due_prospects(cur, limit=50):
    """Get prospects due for next sequence step."""
    return cur.execute("""
        SELECT 
            ps.prospect_id,
            ps.sequence_id,
            ps.current_step,
            ps.variant,
            ps.started_at,
            bo.email,
            bo.business_name,
            bo.metro,
            bo.niche,
            s.sequence_type,
            ss.step_number,
            ss.day_offset,
            ss.kind,
            ss.subject_template,
            ss.body_template,
            ss.html_template
        FROM prospect_sequences ps
        JOIN email_sequences s ON ps.sequence_id = s.id
        JOIN sequence_steps ss ON ss.sequence_id = s.id AND ss.step_number = ps.current_step + 1
        JOIN si_buyer_outreach bo ON bo.prospect_id = ps.prospect_id
        WHERE ps.status = 'active'
          AND s.active = 1
          AND (ps.current_step = 0 OR 
               datetime(ps.started_at, '+' || (SELECT day_offset FROM sequence_steps WHERE sequence_id = s.id AND step_number = ps.current_step) || ' days') <= datetime('now'))
          AND ps.current_step < (SELECT MAX(step_number) FROM sequence_steps WHERE sequence_id = s.id)
        ORDER BY ps.started_at
        LIMIT ?
    """, (limit,)).fetchall()

def queue_email(cur, prospect, step_data, variant):
    """Queue email in si_outbox with branded template."""
    pid = prospect[0]
    email = prospect[5]
    name = prospect[6]
    metro = prospect[7]
    niche = prospect[8]
    step_num = step_data[10]
    day_offset = step_data[11]
    kind = step_data[12]
    subject_tpl = step_data[13]
    body_tpl = step_data[14]
    html_tpl = step_data[15]
    
    biz_short = (name or "lead").lower().replace(" ", "")[:20]
    
    subject = subject_tpl.format(
        name=name or "there",
        metro=metro or "your area",
        niche=niche or "home services",
        business_name=name or "your business",
        business_short=biz_short
    )
    
    body = body_tpl.format(
        name=(name or "there").split()[0] if name else "there",
        metro=metro or "your area",
        niche=niche or "home services",
        business_name=name or "your business",
        business_short=biz_short
    )
    
    # Load HTML template
    html_body = None
    if html_tpl:
        template = get_template(html_tpl)
        if template:
            html_body = template.format(
                business_name=name or "your business",
                business_short=biz_short,
                city=metro or "your city",
                niche=niche or "home services",
                custom_body=body.replace("\n", "<br>")
            )
    
    meta = json.dumps({
        "sequence_id": prospect[1],
        "step": step_num,
        "kind": kind,
        "variant": variant,
        "niche": niche,
        "metro": metro
    })
    
    cur.execute("""
        INSERT INTO si_outbox (to_email, subject, body, html_body, source, status, created_at, meta_json)
        VALUES (?, ?, ?, ?, 'sequence_engine', 'pending', ?, ?)
    """, (email, subject, body, html_body or body, now(), meta))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()
    
    print(f"[sequence_engine] limit={args.limit} dry_run={args.dry_run}")
    
    c = sqlite3.connect(DB)
    cur = c.cursor()
    
    prospects = get_due_prospects(cur, args.limit)
    print(f"[sequence_engine] due: {len(prospects)}")
    
    for p in prospects:
        pid, seq_id, current_step, variant, started_at = p[0], p[1], p[2], p[3], p[4]
        
        # Check if enough time has passed since last step
        if current_step > 0:
            last_step_day = cur.execute("SELECT day_offset FROM sequence_steps WHERE sequence_id=? AND step_number=?", 
                                         (seq_id, current_step)).fetchone()
            if last_step_day:
                due_date = datetime.fromisoformat(started_at.replace('Z', '+00:00')) + timedelta(days=last_step_day[0])
                if datetime.now(timezone.utc) < due_date:
                    continue
        
        kind = p[12]
        
        if args.dry_run:
            print(f"  [dry] {p[5]} step{current_step+1} {kind} ({variant})")
        else:
            queue_email(cur, p, p, variant)
            # Advance step
            cur.execute("UPDATE prospect_sequences SET current_step=?, updated_at=? WHERE prospect_id=? AND sequence_id=?",
                       (current_step + 1, now(), pid, seq_id))
            print(f"  [send] {p[5]} step{current_step+1} {kind} ({variant})")
    
    if not args.dry_run:
        c.commit()
    print(f"[sequence_engine] done")

if __name__ == "__main__":
    main()