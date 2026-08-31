#!/usr/bin/env python3
"""Idempotent schema bootstrap for the 5-phase Omega pipeline.

Creates missing tables + columns in /root/empire_os/empire_os.db:
  lead_source_config, lead_source_sync_log, ai_learning_runs,
  analytics_snapshots, crm_leads.outreach_stage, crm_leads.email_sent_at
Safe to run repeatedly. Run inside empire-hub container (host DB path same).
"""
import sqlite3
import sys

DB = "/root/empire_os/empire_os.db"

DDL = [
    """CREATE TABLE IF NOT EXISTS lead_source_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        name TEXT,
        is_active INTEGER DEFAULT 0,
        access_token TEXT,
        form_id TEXT,
        search_queries TEXT,
        last_sync_at TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS lead_source_sync_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        config_id INTEGER NOT NULL,
        status TEXT,
        leads_fetched INTEGER,
        leads_new INTEGER,
        leads_duplicate INTEGER,
        error_message TEXT,
        started_at TEXT DEFAULT (datetime('now')),
        completed_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ai_learning_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        config_id INTEGER,
        area TEXT,
        input_json TEXT,
        output_json TEXT,
        status TEXT,
        metrics_json TEXT,
        completed_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS analytics_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id TEXT,
        metric_name TEXT,
        metric_value TEXT,
        period_start TEXT,
        period_end TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )""",
    # Omnichannel 4-stage flow tracking (email runway only — socials per founder)
    """CREATE TABLE IF NOT EXISTS outreach_stages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lead_id TEXT NOT NULL,
        channel TEXT DEFAULT 'email',
        stage INTEGER DEFAULT 1,            -- 1=light open 2=numbers 3=diagnosis 4=bridge
        hook TEXT,
        last_msg_at TEXT,
        reply_count INTEGER DEFAULT 0,
        stage_state TEXT DEFAULT 'sent',    -- sent | replied | advanced | booked | closed
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_outreach_stages_lead ON outreach_stages(lead_id)",
    "CREATE INDEX IF NOT EXISTS idx_outreach_stages_state ON outreach_stages(stage_state)",
]

ALTERS = [
    ("crm_leads", "outreach_stage", "INTEGER DEFAULT 1"),
    ("crm_leads", "email_sent_at", "TEXT"),
    ("crm_leads", "email_sent", "INTEGER DEFAULT 0"),
    ("crm_leads", "outreach_attempted", "INTEGER DEFAULT 0"),
    ("crm_leads", "outreach_at", "TEXT"),
]


def main() -> int:
    conn = sqlite3.connect(DB, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    created = []
    for ddl in DDL:
        conn.execute(ddl)
    for table, col, decl in ALTERS:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        if col not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
            created.append(f"{table}.{col}")
    # Seed one inactive config per source so discovery has rows to gate on
    for src in ("serper", "facebook", "linkedin", "google"):
        conn.execute(
            "INSERT INTO lead_source_config (source, name, is_active) "
            "SELECT ?, ?, 0 WHERE NOT EXISTS "
            "(SELECT 1 FROM lead_source_config WHERE source = ?)", (src, src.title(), src))
    conn.commit()
    names = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE name IN "
        "('lead_source_config','lead_source_sync_log','ai_learning_runs',"
        "'analytics_snapshots','outreach_stages')").fetchall()]
    print("tables_ok:", sorted(names))
    print("cols_added:", created)
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
