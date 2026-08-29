#!/usr/bin/env python3
"""Re-ingest surviving AEO pages into empire_os.db (aeo_pages table).

Pages were wiped from the DB in the corruption event but survive on
filesystem: /srv/aeo/{niche}/... and /root/empire_os/scripts/_aeo_pages/...
This restores queryability + feeds the AEO monitor/surface agents.

Usage:
    python3 scripts/ingest_aeo_pages.py            # dry-run count
    python3 scripts/ingest_aeo_pages.py --live     # write
"""
from __future__ import annotations
import os, re, sqlite3, sys
from pathlib import Path

DB_PATH = os.getenv("DB_PATH", "/root/empire_os/empire_os.db")
SOURCES = [
    Path("/srv/aeo"),
    Path("/root/empire_os/scripts/_aeo_pages"),
    Path("/root/empire_os/empire_os/_aeo_pages"),
]

HTML_RE = re.compile(r"\.html?$")

def discover():
    rows = []
    for base in SOURCES:
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if p.is_file() and HTML_RE.search(p.name):
                rel = p.relative_to(base)
                # niche = first path segment
                niche = rel.parts[0] if len(rel.parts) > 1 else "unknown"
                try:
                    body = p.read_text(errors="ignore")
                except Exception:
                    body = ""
                title = ""
                m = re.search(r"<title>(.*?)</title>", body, re.I | re.S)
                if m:
                    title = m.group(1).strip()
                rows.append((str(p), niche, title, len(body)))
    return rows

def main():
    live = "--live" in sys.argv
    rows = discover()
    print(f"[ingest_aeo] discovered {len(rows)} html pages across {len(SOURCES)} sources")

    if not live:
        # group by source dir
        from collections import Counter
        c = Counter()
        for path, niche, _, _ in rows:
            for s in SOURCES:
                if str(s) in path:
                    c[str(s)] += 1
                    break
        for k, v in c.items():
            print(f"  {v:5d}  {k}")
        print("[ingest_aeo] DRY-RUN (no writes). Pass --live to persist.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS aeo_pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT UNIQUE,
            niche TEXT,
            title TEXT,
            bytes INTEGER,
            ingested_at TEXT DEFAULT (datetime('now'))
        )
    """)
    n = 0
    for path, niche, title, size in rows:
        try:
            conn.execute(
                "INSERT OR REPLACE INTO aeo_pages (path, niche, title, bytes) VALUES (?,?,?,?)",
                (path, niche, title, size),
            )
            n += 1
        except Exception as e:
            print(f"  SKIP {path}: {e}")
    conn.commit()
    conn.close()
    print(f"[ingest_aeo] LIVE: wrote {n} pages to aeo_pages")

if __name__ == "__main__":
    main()
