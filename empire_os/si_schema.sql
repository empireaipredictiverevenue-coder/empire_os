-- Empire OS Phase 2 — SI Brain schema
-- Applied toSQLite (empire_os.db). Mirrors PostgreSQL spec tables.

CREATE TABLE IF NOT EXISTS si_strategies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    archetype TEXT NOT NULL,
    genome TEXT NOT NULL DEFAULT '{}',
    win_rate REAL DEFAULT 0.0,
    revenue_generated REAL DEFAULT 0.0,
    confidence REAL DEFAULT 0.0,
    active INTEGER DEFAULT 1,
    generations INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS si_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id INTEGER NOT NULL,
    calls_generated INTEGER DEFAULT 0,
    revenue_captured REAL DEFAULT 0.0,
    win INTEGER DEFAULT 0,
    meta TEXT DEFAULT '{}',
    recorded_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (strategy_id) REFERENCES si_strategies(id)
);

CREATE TABLE IF NOT EXISTS si_parameters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subsystem TEXT NOT NULL,
    param_key TEXT NOT NULL,
    param_value REAL DEFAULT 0.0,
    source TEXT DEFAULT 'si',
    adopted_at TEXT DEFAULT (datetime('now')),
    UNIQUE (subsystem, param_key)
);

CREATE TABLE IF NOT EXISTS si_adaptation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subsystem TEXT NOT NULL,
    param_key TEXT NOT NULL,
    old_value REAL,
    new_value REAL,
    reason TEXT DEFAULT '',
    logged_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS si_evolution_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    detail TEXT DEFAULT '{}',
    logged_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (strategy_id) REFERENCES si_strategies(id)
);

CREATE TABLE IF NOT EXISTS si_media_assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    objective TEXT NOT NULL,
    target_company TEXT DEFAULT '',
    asset_path TEXT DEFAULT '',
    asset_type TEXT DEFAULT 'video',
    status TEXT DEFAULT 'pending',
    meta TEXT DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS si_health_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    component TEXT NOT NULL,
    metric TEXT NOT NULL,
    value REAL DEFAULT 0.0,
    logged_at TEXT DEFAULT (datetime('now'))
);

-- Seed base archetypes
INSERT OR IGNORE INTO si_strategies (name, archetype, genome, active)
VALUES
  ('aggressive_strike_v1', 'AGGRESSIVE_STRIKE', '{"intensity":0.9,"radius_mi":25,"budget_usd":1500,"channel":"video"}', 1),
  ('ugly_banner_v1', 'UGLY_BANNER', '{"intensity":0.5,"radius_mi":15,"budget_usd":400,"channel":"display"}', 1);
