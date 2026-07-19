"""
Empire OS v3 - SEO Agent (traditional)
======================================

Pulls open-source SEO patterns. Runs basic on-page audits against
/aeo/* pages and reports issues to /root/feedback/seo_log.jsonl +
surfaces to /v1/seo/audit.

Cadence: 4h.
"""
import json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")
import requests

HUB  = os.environ.get("HUB_URL", "http://127.0.0.1:8081")
FB   = Path("/root/feedback")
LOG  = FB / "seo_log.jsonl"
INTERVAL = int(os.environ.get("INTERVAL_SEC", str(4 * 3600)))


def log(level, msg, **fields):
    e = {"ts": datetime.now(timezone.utc).isoformat(),
         "level": level, "msg": msg, **fields}
    FB.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(e) + "\n")
    if level in ("ERROR", "EVENT", "WARN"):
        print(json.dumps(e), flush=True)


def fetch_via_hub() -> list:
    try:
        r = requests.get(f"{HUB}/v1/swarm/audit-log?n=200",
                         timeout=8).json()
        urls = [e.get("url", "")
                for e in r.get("events", [])]
        return list(set([u for u in urls
                         if u.startswith("/aeo/")]))[:40]
    except Exception:
        return []


def audit(url: str) -> dict:
    full = f"http://127.0.0.1:8081{url}"
    try:
        r = requests.get(full, timeout=8)
        status = r.status_code
        html = r.text
    except Exception as e:
        return {"url": url, "error": str(e)[:160]}
    return {
        "url": url,
        "status": status,
        "size_bytes": len(html),
        "title_count": html.count("<title>"),
        "h1_count":    html.count("<h1"),
        "h2_count":    html.count("<h2"),
        "img_missing_alt":
                     html.count("<img") - html.count("alt="),
        "links_total": html.count("<a href") - html.count('<a href="#"'),
        "audited_at":  datetime.now(timezone.utc).isoformat(),
    }


def push_fix_blueprint(niche, issues):
    """Surface a weak AEO page to Cortex as an aeo:fix blueprint (active loop)."""
    try:
        import sqlite3, json as _j, time as _t
        db = os.environ.get("EMPIRE_DB", "/root/empire_os/empire_os.db")
        c = sqlite3.connect(db)
        bid = f"aeo_fix_{niche}_{int(_t.time())}"
        c.execute(
            "INSERT INTO cortex_blueprints "
            "(blueprint_id, campaign_type, visual_dna, script_dna, niche, created_at) "
            "VALUES (?, 'aeo:fix', '{}', ?, ?, ?)",
            (bid, _j.dumps({"niche": niche, "issues": issues,
                            "status": "pending"}), niche,
             datetime.now(timezone.utc).isoformat()))
        c.commit()
        c.close()
    except Exception as e:
        log("WARN", "fix_blueprint_fail", err=str(e)[:120])


def cycle():
    urls = fetch_via_hub()
    if not urls:
        urls = [
            "/aeo/plumbing/NYC",
            "/aeo/hvac/NYC",
            "/aeo/roofing/NYC",
            "/aeo/electrical/NYC",
            "/aeo/landscaping/NYC",
            "/aeo/painting/NYC",
            "/aeo/water_damage_remediation/NYC",
            "/aeo/mold_remediation/NYC",
            "/aeo/pest_control/NYC",
            "/aeo/general_contractor/NYC",
            "/signup",
        ]
    log("CYCLE_START", "seo cycle", urls=len(urls))
    results = [audit(u) for u in urls]
    avg_size = sum(r.get("size_bytes", 0)
                   for r in results) // max(len(results), 1)
    issues = sum(max(r.get("img_missing_alt", 0), 0)
                 for r in results)
    # emit Cortex fix-blueprints for pages with on-page problems
    for r in results:
        niche = r.get("url", "").split("/")[2] if "/aeo/" in r.get("url", "") else None
        if not niche:
            continue
        page_issues = {k: r.get(k) for k in
                       ("img_missing_alt", "h2_count", "title_count", "h1_count")
                       if r.get(k)}
        if r.get("img_missing_alt", 0) or r.get("title_count", 0) == 0 \
           or r.get("h2_count", 0) == 0:
            push_fix_blueprint(niche, page_issues)
    log("CYCLE", "seo_done",
        scanned=len(results), avg_size=avg_size,
        titles_found=sum(1 for r in results if r.get("title_count")),
        issues=issues)
    try:
        requests.post(f"{HUB}/v1/seo/audit",
                      json={"results": results,
                            "ts": datetime.now(timezone.utc).isoformat()},
                      timeout=8)
    except Exception as e:
        log("WARN", "audit_post_fail", err=str(e)[:120])


if __name__ == "__main__":
    print(f"[{datetime.now(timezone.utc).isoformat()}] seo-agent online — {INTERVAL}s",
          flush=True)
    while True:
        try:
            cycle()
        except Exception as e:
            log("ERROR", "cycle", err=str(e)[:200])
        time.sleep(INTERVAL)
