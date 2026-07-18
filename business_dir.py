#!/usr/bin/env python3
"""
Agent Directory — businesses pay to be discoverable by agents via MCP.

JSON-backed store (no DB schema change). Each business:
  name, niche, city, blurb, tenant_slug

register(name, niche, city, blurb, tenant) -> entry
list(niche=None) -> matching businesses (all if niche omitted)
"""
import json, os, time

STORE = "/root/feedback/business_dir.json"


def _load():
    if not os.path.exists(STORE):
        return []
    try:
        return json.load(open(STORE))
    except Exception:
        return []


def _save(rows):
    os.makedirs(os.path.dirname(STORE), exist_ok=True)
    json.dump(rows, open(STORE, "w"), indent=2)


def register(name, niche, city, blurb, tenant):
    """Add/update a business listing. tenant_slug is the unique key."""
    rows = _load()
    slug = tenant.strip().lower().replace(" ", "-")
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    entry = {"name": name, "niche": niche, "city": city,
             "blurb": blurb, "tenant_slug": slug, "listed_at": now}
    for i, r in enumerate(rows):
        if r.get("tenant_slug") == slug:
            rows[i] = entry
            _save(rows)
            return {**entry, "updated": True}
    rows.append(entry)
    _save(rows)
    return {**entry, "updated": False}


def list(niche=None):
    """Return businesses. If niche given, match case-insensitively on niche."""
    rows = _load()
    if niche:
        n = niche.strip().lower()
        rows = [r for r in rows if r.get("niche", "").strip().lower() == n]
    return {"count": len(rows), "niche": niche, "businesses": rows}
