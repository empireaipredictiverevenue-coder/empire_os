-- Analytics + link-cloak schema (Phase 1). Run via sqlite3 on empire_os.db.
PRAGMA busy_timeout=30000;

CREATE TABLE IF NOT EXISTS lead_clicks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT UNIQUE NOT NULL,
    email TEXT,
    url TEXT NOT NULL,
    source TEXT,
    ip TEXT,
    user_agent TEXT,
    clicked_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_lead_clicks_email ON lead_clicks(email);
CREATE INDEX IF NOT EXISTS idx_lead_clicks_token ON lead_clicks(token);

CREATE TABLE IF NOT EXISTS email_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    event TEXT NOT NULL,            -- open | click | sent | bounce | unsub
    campaign TEXT,
    meta_json TEXT,
    ts TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_email_events_email ON email_events(email);
CREATE INDEX IF NOT EXISTS idx_email_events_event ON email_events(event);

CREATE TABLE IF NOT EXISTS replies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inbound_id TEXT,
    email TEXT NOT NULL,
    body TEXT,
    subject TEXT,
    ts TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_replies_email ON replies(email);

CREATE TABLE IF NOT EXISTS unsubscribes (
    email TEXT PRIMARY KEY,
    reason TEXT,
    ts TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS link_redirects (
    token TEXT PRIMARY KEY,
    target TEXT NOT NULL,
    source TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
