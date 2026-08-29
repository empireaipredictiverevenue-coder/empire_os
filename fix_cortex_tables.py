import sqlite3
db = "/root/empire_os/empire_os.db"
c = sqlite3.connect(db)
c.executescript("""
CREATE TABLE IF NOT EXISTS cortex_api_keys (
    api_key TEXT UNIQUE,
    tenant_id TEXT,
    email TEXT,
    plan TEXT DEFAULT 'free',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS cortex_usage (
    id INTEGER PRIMARY KEY,
    api_key TEXT,
    endpoint TEXT,
    ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS si_tenant (
    tenant_id TEXT PRIMARY KEY,
    name TEXT,
    email TEXT,
    api_key TEXT,
    plan TEXT DEFAULT 'free',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")
c.commit()
rows = [r[0] for r in c.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'cortex%' OR name='si_tenant'")]
print("OK created/confirmed:", rows)
c.close()
