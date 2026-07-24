#!/root/venv/bin/python
"""Schema migration runner for Empire OS."""
import sqlite3, os, sys
from datetime import datetime

DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), "empire_os.db")
MIGRATIONS = {}

def run_migration(name, sql):
    MIGRATIONS[name] = sql

# --- Migration: omega_score ---
run_migration("2026-07-23_omega_score", """
    ALTER TABLE crm_leads ADD COLUMN omega_score REAL DEFAULT 0;
""")

# --- Migration: solana_failed_tx ---
run_migration("2026-07-23_solana_dlq", """
    CREATE TABLE IF NOT EXISTS solana_failed_tx (
        sig TEXT PRIMARY KEY,
        payload TEXT,
        error TEXT,
        retry_count INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now'))
    );
""")

# --- Migration: correlation_ids ---
run_migration("2026-07-23_correlation_ids", """
    ALTER TABLE crm_leads ADD COLUMN correlation_id TEXT;
""")

# --- Migration: enrichment_log ---
run_migration("2026-07-23_enrichment_log", """
    CREATE TABLE IF NOT EXISTS enrichment_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lead_uid TEXT,
        provider TEXT,
        result TEXT,
        cost_cents REAL,
        latency_ms INTEGER,
        created_at TEXT DEFAULT (datetime('now'))
    );
""")

def main():
    conn = sqlite3.connect(DB)
    conn.execute("CREATE TABLE IF NOT EXISTS _migrations (name TEXT PRIMARY KEY, applied_at TEXT)")
    applied = {r[0] for r in conn.execute("SELECT name FROM _migrations").fetchall()}
    
    for name, sql in MIGRATIONS.items():
        if name in applied:
            print(f"SKIP  {name}")
            continue
        try:
            conn.executescript(sql)
            conn.execute("INSERT INTO _migrations (name, applied_at) VALUES (?, ?)", (name, datetime.utcnow().isoformat()))
            conn.commit()
            print(f"OK    {name}")
        except Exception as e:
            conn.rollback()
            print(f"FAIL  {name}: {e}")
    conn.close()

if __name__ == "__main__":
    main()
