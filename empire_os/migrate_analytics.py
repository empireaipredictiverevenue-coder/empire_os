import sqlite3
DB = "/root/empire_os/empire_os.db"
c = sqlite3.connect(DB)
c.execute("PRAGMA busy_timeout=30000")
c.executescript("""
DROP TABLE IF EXISTS lead_clicks;
DROP TABLE IF EXISTS email_events;
DROP TABLE IF EXISTS replies;
DROP TABLE IF EXISTS unsubscribes;
DROP TABLE IF EXISTS link_redirects;

CREATE TABLE lead_clicks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT,
    email TEXT,
    url TEXT,
    source TEXT,
    ip TEXT,
    user_agent TEXT,
    clicked_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_lead_clicks_email ON lead_clicks(email);
CREATE INDEX idx_lead_clicks_token ON lead_clicks(token);

CREATE TABLE email_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    event TEXT NOT NULL,
    campaign TEXT,
    meta_json TEXT,
    ts TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_email_events_email ON email_events(email);
CREATE INDEX idx_email_events_event ON email_events(event);

CREATE TABLE replies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inbound_id TEXT,
    email TEXT NOT NULL,
    body TEXT,
    subject TEXT,
    ts TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_replies_email ON replies(email);

CREATE TABLE unsubscribes (
    email TEXT PRIMARY KEY,
    reason TEXT,
    ts TEXT DEFAULT (datetime('now'))
);

CREATE TABLE link_redirects (
    token TEXT PRIMARY KEY,
    target TEXT NOT NULL,
    source TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
""")
c.commit()
c.close()
print("analytics tables rebuilt (new schema)")
