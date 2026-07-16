#!/usr/bin/env python3
"""White-label config for Empire OS tenants.
Lightweight: per-tenant brand (name, logo, colors, domain) stored + accessed.
The tenant `white_label` feature flag (tenants.py) gates access.
Portal/email rendering reads get_brand(tenant_id) to swap branding.
"""
import sqlite3, json

DB = "/root/empire_os/empire_os.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS si_whitelabel (
    tenant_id   TEXT PRIMARY KEY,
    brand_name  TEXT,
    logo_url    TEXT,
    primary_color TEXT DEFAULT '#39ff88',
    domain      TEXT,
    config_json TEXT DEFAULT '{}',
    created_at  TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%f','now'))
);
"""

def init():
    c = sqlite3.connect(DB, timeout=15)
    c.executescript(SCHEMA); c.commit(); c.close()

def set_brand(tenant_id, brand_name, logo_url="", primary_color="#39ff88", domain="", config=None):
    init()
    c = sqlite3.connect(DB, timeout=15)
    c.execute("INSERT OR REPLACE INTO si_whitelabel "
              "(tenant_id, brand_name, logo_url, primary_color, domain, config_json) "
              "VALUES (?,?,?,?,?,?)",
              (tenant_id, brand_name, logo_url, primary_color, domain, json.dumps(config or {})))
    c.commit(); c.close()

def get_brand(tenant_id):
    c = sqlite3.connect(DB, timeout=15)
    row = c.execute("SELECT brand_name, logo_url, primary_color, domain, config_json "
                    "FROM si_whitelabel WHERE tenant_id=?", (tenant_id,)).fetchone()
    c.close()
    if not row: return None
    return {"brand_name": row[0], "logo_url": row[1],
            "primary_color": row[2], "domain": row[3],
            "config": json.loads(row[4] or "{}")}

if __name__ == "__main__":
    init()
    print("whitelabel schema ready")
