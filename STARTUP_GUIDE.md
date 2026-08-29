# Empire OS Hub — Startup & Fixcheck Guide

## Start hub (port 8081 — NOT 8000/8080)

```bash
incus exec empire-hub -- bash -c "EMPIRE_PORT=8081 /root/venv/bin/python3 -m empire_os.hub --port 8081 --host 0.0.0.0"
```

Run as background service with logs:

```bash
incus exec empire-hub -- bash -c "EMPIRE_PORT=8081 /root/venv/bin/python3 -m empire_os.hub --port 8081 --host 0.0.0.0 > /tmp/hub.log 2>&1"
```

Kill all running hub instances before restart:

```bash
incus exec empire-hub -- pkill -f "empire_os.hub"
```

## Health checks

```bash
# VALID endpoint (returns 200)
incus exec empire-hub -- curl -s http://127.0.0.1:8081/health
# -> {"status":"online","engine":"empire-os-v3","version":"0.1.0"}

# WRONG endpoint (returns 404 — do NOT use for health)
# /healthz  -> 404 Not Found
```

Container IP from host: `10.118.155.218:8081`
From inside container use `127.0.0.1:8081` (localhost resolves but bind is 0.0.0.0).

## Fixcheck — known failure modes

### 1. `/v1/leads/direct` returns 500: `DB write failed: table lane_leads has no column named niche`

Root cause: fresh DB created via `SQLiteBackend.ensure_schema()` does NOT add `niche`/`metro` columns to `lane_leads` (those live in `empire_os/lanes.py` schema, applied at a different call). The direct-intake route at `hub.py:1586` INSERTs `niche, metro`.

Fix:
```bash
incus exec empire-hub -- sqlite3 /root/empire_os/empire_os.db \
  "ALTER TABLE lane_leads ADD COLUMN niche TEXT; ALTER TABLE lane_leads ADD COLUMN metro TEXT;"
```
Idempotent — re-run safe (duplicate column errors are harmless).

### 2. `/v1/leads/direct` returns 500: `sqlite3.DatabaseError: database disk image is malformed`

Root cause: DB page corruption (invalid page numbers in B-tree). Triggered by `evidence_payload.build_taxonomy -> _consent_by_niche`.

Fix: rebuild fresh DB, lose data (no usable `.recover` on this image):
```bash
incus exec empire-hub -- mv /root/empire_os/empire_os.db /root/empire_os/empire_os.db.corrupt
incus exec empire-hub -- bash -c "cd /root/empire_os && /root/venv/bin/python3 -c 'from empire_os.hub import SQLiteBackend; b=SQLiteBackend(\"empire_os.db\"); b.ensure_schema(); print(\"Schema created\")'"
# then re-apply fix #1 (niche/metro columns)
```
Then restart hub.

### 3. `outbox_pending` / `/v1/outbox/pending` errors: `no such column: o.html_body`

Root cause: `si_outbox` table created without `html_body` column, but `outbox_pending` SELECT at `hub.py:6124` references it. CREATE TABLE at `hub.py:1076` already declares `html_body`.

Fix (live DB):
```bash
incus exec empire-hub -- sqlite3 /root/empire_os/empire_os.db \
  "ALTER TABLE si_outbox ADD COLUMN html_body TEXT;"
```

### 4. hub binds wrong port / silent fail

Must set `EMPIRE_PORT=8081` env. Default binds 8080 → conflict / wrong port. Always pass `--port 8081` AND `EMPIRE_PORT=8081`.

## Verify after restart

```bash
incus exec empire-hub -- curl -s http://127.0.0.1:8081/health
incus exec empire-hub -- curl -s http://127.0.0.1:8081/v1/leads/direct \
  -H "Content-Type: application/json" \
  -d '{"niche":"roofing","metro":"DALLAS"}'
# -> {"ok":true,"lead_id":"lead_...","db_id":N,...,"status":"pending"}
```

## Key paths

- Hub code: `/root/empire_os/empire_os/hub.py`
- DB: `/root/empire_os/empire_os.db`
- Lane schema: `/root/empire_os/empire_os/lanes.py` (`ensure_schema`, `seed_lanes`)
- Container: `empire-hub` (incus), IP `10.118.155.218`
- Venv: `/root/venv/bin/python3`

## Revenue context (vault / contract)

- USDT (BSC) vault: `0x1339b487046B0ad924a10c20b1791608EA8595a8`
- USDT contract (BSC): `0x55d398326f99059fF775485246999027B3197955`
- Listener: `/root/empire_os/scripts/bsc_usdt_listener_fixed.py` (verified 7/7)
- Pending invoices: 24,291. Buyer_leads pending re-delivery: 581,142.
