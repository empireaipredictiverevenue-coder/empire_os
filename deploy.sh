#!/usr/bin/env bash
# deploy.sh — sync host empire_os code into the empire-hub incus container
# and restart the running services. Prevents host/container code drift
# (the root cause of the stale 'simulated' charge bug).
#
# Usage:  ./deploy.sh [--no-restart] [--smoke]
set -uo pipefail

CONTAINER="empire-hub"
HOST_REPO="/root/empire_os"
HOST_SRC="${HOST_REPO}/empire_os"
CT_SRC="/root/empire_os/empire_os"
RESTART=1
SMOKE=0

for arg in "$@"; do
  case "$arg" in
    --no-restart) RESTART=0 ;;
    --smoke)      SMOKE=1 ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

# sanity: container must exist
if ! incus list -c n --format csv | grep -qx "$CONTAINER"; then
  echo "FATAL: container '$CONTAINER' not found via 'incus list'" >&2
  exit 3
fi

echo "==> pushing host ${HOST_SRC}/*.py -> ${CONTAINER}:${CT_SRC}"
pushed=0
while IFS= read -r f; do
  rel="${f#${HOST_SRC}/}"                       # strip absolute host prefix
  incus file push "$f" "${CONTAINER}${CT_SRC}/${rel}" >/dev/null 2>&1 \
    && { printf '.'; pushed=$((pushed+1)); } \
    || { echo "  FAILED: $rel" >&2; }
done < <(find "$HOST_SRC" -name '*.py' -not -path '*/skills_library/*')
echo " pushed ${pushed} files"

if [[ "$RESTART" -eq 1 ]]; then
  echo "==> restarting pm2 services in ${CONTAINER}"
  incus exec "$CONTAINER" -- pm2 restart empire-hub-service empire-solana-listener empire-north-mini 2>&1 \
    | grep -E "restarting|online" || true
  # poll /health up to 15s (hub may take a few sec to rebind)
  ready=0
  for i in $(seq 1 15); do
    code=$(incus exec "$CONTAINER" -- curl -s -m 4 -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/health 2>/dev/null || true)
    if [[ "$code" == "200" ]]; then ready=1; break; fi
    sleep 4
  done
  if [[ "$ready" -ne 1 ]]; then
    echo "WARN: hub /health not 200 after 15s (last=$code) — smoke may be unreliable"
  fi
fi

if [[ "$SMOKE" -eq 1 ]]; then
  echo "==> smoke: hub ready (health polled 200 above)"
  echo "==> smoke: charge -> replay cycle (NO-SIM + settlement + FK)"
  incus exec "$CONTAINER" -- bash -c 'cd /root/empire_os && /root/venv/bin/python3 - <<PYEOF
import sqlite3, sys, json, urllib.request
sys.path.insert(0, "/root/empire_os")
from empire_os.charge import charge
con = sqlite3.connect("/root/empire_os/empire_os.db"); con.row_factory = sqlite3.Row
pid = con.execute("SELECT prospect_id FROM si_buyer_outreach WHERE email LIKE \"%@%\" ORDER BY score DESC LIMIT 1").fetchone()[0]
res = charge(buyer_id=pid, head=2, reason="deploy_smoke", amount_cents=100, currency="USDC", force_processor="usdc")
ch = con.execute("SELECT status FROM si_charges WHERE charge_id=?", (res["charge_id"],)).fetchone()
inv = con.execute("SELECT invoice_id, status, charge_id FROM si_ppc_invoices WHERE charge_id=?", (res["charge_id"],)).fetchone()
assert ch["status"] == "open", "charge not open: %s" % ch["status"]
assert inv is not None and inv["status"] == "open", "invoice not created under shared charge_id"
assert inv["charge_id"] == res["charge_id"], "charge_id FK mismatch"
iid = inv["invoice_id"]
body = json.dumps({"amount_usdc":1.0,"memo":"INV_%s" % iid,"wallet_from":"deploy_smoke","force_status":"paid"}).encode()
req = urllib.request.Request("http://127.0.0.1:8000/v1/finance/replay", data=body, headers={"Content-Type":"application/json"})
rj = json.loads(urllib.request.urlopen(req, timeout=10).read())
assert rj.get("paid_invoice_id") == iid, "replay matched wrong: %s" % rj
sett = con.execute("SELECT prospect_id FROM si_settlements WHERE prospect_id=?", (iid,)).fetchone()
assert sett is not None, "settlement not written"
print("SMOKE OK: charge=%s invoice=%s settled=yes" % (res["charge_id"], iid))
con.execute("DELETE FROM si_settlements WHERE prospect_id=?", (iid,))
con.execute("DELETE FROM si_ppc_invoices WHERE invoice_id=?", (iid,))
con.execute("DELETE FROM si_charges WHERE charge_id=?", (res["charge_id"],))
con.commit()
print("SMOKE CLEANED")
PYEOF'
fi

echo "==> deploy complete"
