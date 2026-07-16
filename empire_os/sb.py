"""Minimal PostgREST-backed DB layer for Empire OS.

Replaces sqlite3.connect(...) for the shared hub/agent DB. Uses the Supabase
REST API (PostgREST) over IPv4 so it works from IPv4-only hosts (Vultr) without
needing the IPv6 direct connection or the connection pooler host.

Reads config from environment (set in /root/empire_os/.env):
    SUPABASE_URL            https://<ref>.supabase.co
    SUPABASE_SERVICE_KEY    service_role key (bypasses RLS)
Optionally a table-name alias map can be supplied to keep old sqlite table
names working while the Postgres tables differ.

All functions return plain dicts/lists or raise on HTTP error.
"""
from __future__ import annotations
import os
import json
import urllib.request
import urllib.error

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

# sqlite table name -> postgres table name
ALIAS = {
    "si_outbox": "outbox_messages",
}


def _table(name: str) -> str:
    return ALIAS.get(name, name)


def _headers(extra: dict | None = None) -> dict:
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def _url(table: str, query: str = "") -> str:
    return f"{SUPABASE_URL}/rest/v1/{_table(table)}{query}"


def select(table: str, columns: str = "*", filters: dict | None = None,
           order: str | None = None, limit: int = 1000, offset: int = 0) -> list:
    """SELECT rows. filters = {col: value} -> col=eq.value."""
    q = f"?select={columns}"
    if filters:
        for k, v in filters.items():
            q += f"&{k}=eq.{v}"
    if order:
        q += f"&order={order}"
    q += f"&offset={offset}&limit={limit}"
    req = urllib.request.Request(_url(table, q), headers=_headers())
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def insert(table: str, row: dict, return_repr: bool = True) -> list:
    headers = _headers({"Prefer": "return=representation"} if return_repr else {"Prefer": "return=minimal"})
    data = json.dumps(row).encode()
    req = urllib.request.Request(_url(table), data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode()) if return_repr else []


def update(table: str, match: dict, values: dict) -> list:
    """PATCH rows matching `match` (col:val) with `values`."""
    q = ""
    for k, v in match.items():
        q += f"&{k}=eq.{v}" if q else f"?{k}=eq.{v}"
    headers = _headers({"Prefer": "return=representation"})
    data = json.dumps(values).encode()
    req = urllib.request.Request(_url(table, q), data=data, headers=headers, method="PATCH")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def delete(table: str, match: dict) -> None:
    q = ""
    for k, v in match.items():
        q += f"&{k}=eq.{v}" if q else f"?{k}=eq.{v}"
    req = urllib.request.Request(_url(table, q), headers=_headers(), method="DELETE")
    urllib.request.urlopen(req, timeout=30).close()


def rpc(name: str, params: dict | None = None) -> object:
    data = json.dumps(params or {}).encode()
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/rpc/{name}", data=data,
                                 headers=_headers(), method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())
