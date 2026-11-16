"""Read-only founder-side authenticated probe of NVIDIA isolated evaluation.

Reads generated local bootstrap credentials into memory, never prints or saves
them, and uses only loopback. No settings, data or permissions are changed.
"""
from __future__ import annotations

import json
from pathlib import Path

import httpx

ROOT = Path("/srv/empire_os/runtime/nvidia_ontology_eval")
BASE = "http://localhost:33000"
ENDPOINTS = {
    "session": "/api/auth/get-session",
    "semantic_enabled": "/api/configurations/semantic-compilation",
    "semantic_status": "/api/semantic-compilation/status",
    "catalog_databases": "/api/datasources/dbs",
    "catalog_terms": "/api/terms",
}

def _metadata(payload: object) -> dict:
    if isinstance(payload, list):
        return {"kind": "list", "count": len(payload)}
    if isinstance(payload, dict):
        out = {"kind": "object", "keys": sorted(payload.keys())[:16]}
        for key in ("enabled", "calculated", "running", "last_success_at",
                    "last_failure_at", "status"):
            if key in payload:
                out[key] = payload[key]
        for key in ("data", "items", "databases", "terms"):
            val = payload.get(key)
            if isinstance(val, list):
                out[key + "_count"] = len(val)
                if key == "data":
                    out["database_identifiers"] = [
                        {name: item[name] for name in ("name", "database_name", "db_name") if name in item}
                        for item in val if isinstance(item, dict)
                    ]
        return out
    return {"kind": type(payload).__name__}

def main():
    cfg = dict(line.split("=", 1) for line in
               (ROOT / ".env").read_text().splitlines() if "=" in line)
    with httpx.Client(
        base_url=BASE, timeout=20, follow_redirects=False,
        headers={"Origin": BASE, "Accept": "application/json"},
        trust_env=False,
    ) as client:
        login = client.post("/api/auth/sign-in/email", json={
            "email": cfg["AUTO_ONTOLOGY_ADMIN_EMAIL"],
            "password": cfg["AUTO_ONTOLOGY_ADMIN_PASSWORD"],
        })
        result = {
            "status": "AUTH_READBACK",
            "login_http": login.status_code,
            "session_cookie_present": bool(client.cookies),
            "password_disclosed": False,
            "session_cookie_disclosed": False,
            "endpoints": {},
        }
        if login.status_code not in (200, 201):
            try:
                result["error_code"] = login.json().get("code")
            except Exception:
                result["error_code"] = "nonjson"
            print(json.dumps(result, indent=2))
            return
        for label, path in ENDPOINTS.items():
            try:
                response = client.get(path)
                entry = {"http": response.status_code}
                if response.status_code == 200:
                    try:
                        entry.update(_metadata(response.json()))
                    except ValueError:
                        entry["result"] = "nonjson"
                else:
                    entry["result"] = "not_readable"
            except httpx.HTTPError as exc:
                entry = {"result": type(exc).__name__}
            result["endpoints"][label] = entry
        print(json.dumps(result, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
