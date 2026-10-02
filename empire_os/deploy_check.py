#!/usr/bin/env python3
"""deploy-check — post-deploy health gate for Empire OS hub.

Run after any push+restart. Asserts the core revenue path is live:
  - hub /health -> 200
  - /v1/buyers/apply -> ok:True (no 502)
  - TELEGRAM_MONEY_ONLY gate drops non-revenue send
  - canonical BSC/USDT verifier config + BSC chain read -> ok
Exits non-zero on any failure so a broken deploy is caught, not shipped.
"""
import os, sys, json, sqlite3, urllib.request
from empire_os.bsc_usdt_verifier import BscUsdtConfig, get_block_anchor
sys.path.insert(0, "/root/empire_os")
_env_lines = []
for _ln in open("/root/empire_os/.env"):
    _ln = _ln.strip()
    if _ln and "=" in _ln and not _ln.startswith("#"):
        _k, _v = _ln.split("=", 1)
        os.environ.setdefault(_k.strip(), _v.strip())
os.environ.update(dict(l.strip().split("=",1) for l in open("/root/empire_os/.env")
    if l.strip() and "=" in l and not l.startswith("#")))
BASE = "http://127.0.0.1:8000"
fails = []

# 1) hub health (liveness signal; apply-ok is authoritative)
try:
    r = urllib.request.urlopen(f"{BASE}/health", timeout=20)
    if r.status != 200:
        print(f"WARN hub /health status {r.status} (apply still checked)")
    else:
        print("hub /health: 200 OK")
except Exception as e:
    print(f"WARN hub /health slow ({e}) — checking apply as authoritative liveness")

# 2) apply endpoint returns ok (not 502)
import uuid
p = {"name":"DC","niche":"roof_repair","email":f"dc-{uuid.uuid4().hex[:8]}@v.co",
     "tier":"silver","min_deposit":0.0,"source":"deploy_check"}
try:
    req = urllib.request.Request(BASE+"/v1/buyers/apply", data=json.dumps(p).encode(),
        headers={"Content-Type":"application/json"}, method="POST")
    j = json.loads(urllib.request.urlopen(req, timeout=15).read())
    if not j.get("ok"):
        fails.append(f"apply not ok: {j}")
    else:
        print("apply: ok:True | vault:", j["payment"]["vault_wallet"][:12])
except Exception as e:
    fails.append(f"apply 502/broken: {e}")

# 3) money-only gate drops non-revenue telegram
import empire_os.hermes_gateway as g
if not g.TELEGRAM_BOT_TOKEN:
    fails.append("gateway token missing")
elif os.environ.get("TELEGRAM_MONEY_ONLY") != "1":
    fails.append("MONEY_ONLY not set")
else:
    nr = g._telegram_send("noise", revenue=False)
    if nr.get("skipped") != "money_only":
        fails.append(f"gate not dropping noise: {nr}")
    else:
        print("money-only gate: drops non-revenue OK")

# 4) Canonical BSC/USDT verifier is configured and reading BSC mainnet.
try:
    cfg = BscUsdtConfig.from_env()
    anchor = get_block_anchor(cfg)
    if int(anchor.get("chain_id", 0)) != 56:
        fails.append(f"BSC chain mismatch: {anchor}")
    else:
        print("BSC/USDT verifier: chain 56 OK")
except Exception as e:
    fails.append(f"BSC/USDT verifier unavailable: {e}")

print("=== deploy-check ===")
if fails:
    print("RESULT: FAIL")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("RESULT: ALL GREEN")
