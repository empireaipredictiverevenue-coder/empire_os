#!/usr/bin/env bash
# Empire AI: additive single-purpose private Data Brokerage route release.
# Existing checkout service, data, payments, all financial gates untouched.
# Public gateway is deliberately NOT restarted or enabled by this script.
set -euo pipefail

ROOT=/srv/empire_os
PY="$ROOT/.venv/bin/python"
UNIT="empire-self-serve-checkout.service"
NAME="95-empire-brokerage-premium-discovery-private.conf"
DIR="/etc/systemd/system/$UNIT.d"
CONF="$DIR/$NAME"
PUBLIC="$ROOT/apps/empire-public-site/out/commercial.html"

fail() { echo "BROKERAGE_PRIVATE_RELEASE_HOLD=$1" >&2; exit 2; }

if [[ "${1:-}" != "--preflight" && "${1:-}" != "--apply-founder-approved-private-premium-enquiry" ]]; then
  fail "EXPLICIT_NARROW_FLAG_REQUIRED"
fi

cd "$ROOT"
[[ -f empire_os/data_brokerage_premium_private_service.py ]] || fail MISSING_RELEASE_MODULE
[[ -f empire_os/data_brokerage_premium_public_service.py ]] || fail MISSING_PUBLIC_ADAPTER
[[ -f "$PUBLIC" ]] || fail LIVE_SITE_MISSING
[[ -z "$(git status --porcelain -- empire_os/data_brokerage_premium_private_service.py empire_os/data_brokerage_premium_public_service.py)" ]] || fail UNCOMMITTED_RELEASE_MODULES
systemctl is-active --quiet "$UNIT" || fail EXISTING_CHECKOUT_NOT_ACTIVE
systemctl is-active --quiet empire-public-gateway.service || fail EXISTING_GATEWAY_NOT_ACTIVE

# Do not silently build/rewrite ASTRA's live static public assets.
[[ -f "$ROOT/apps/empire-public-site/src/components/BrokeragePremiumDiscovery.tsx" ]] || fail UI_SOURCE_MISSING
"$PY" -B -m pytest -q   tests/test_data_brokerage_premium_service_mounts_20261018.py   tests/test_data_brokerage_premium_enquiry_20261018.py   tests/test_data_brokerage_premium_gateway_adapter_20261018.py >/dev/null || fail CONTRACT_REGRESSION

# Baseline unit must still have its exact existing module. Never replace
# another owner's concurrently released checkout entrypoint or drop-in.
if [[ -e "$CONF" ]]; then
  fail ALREADY_RELEASED_OR_FOREIGN_DROPIN
fi
if ! systemctl show -p ExecStart --value "$UNIT" | grep -Fq 'empire_os.self_serve_checkout_api:app'; then
  fail OTHER_OWNER_CHECKOUT_EXECSTART_CHANGED
fi
if ! curl -fsS --max-time 5 http://127.0.0.1:8098/v1/commercial/offers | "$PY" -c '
import json,sys
x=json.load(sys.stdin)
assert x.get("status")=="FOUNDER_LED_ENQUIRY_AVAILABLE"
assert any(o.get("product_code")=="competitor_search_gap" for o in x["offers"])
' ; then
  fail EXISTING_COMMERCE_API_CHANGED
fi
echo "BROKERAGE_PRIVATE_RELEASE_PREFLIGHT_PASS (no website or payment changes)"

if [[ "${1:-}" == "--preflight" ]]; then exit 0; fi
[[ "${EUID:-$(id -u)}" == 0 ]] || fail ROOT_REQUIRED_FOR_NARROW_SYSTEMD_DROPIN

mkdir -p "$DIR"
trap 'st=$?; if [[ "$st" -ne 0 && -f "$CONF" ]]; then
  echo "BROKERAGE_PRIVATE_RELEASE_ROLLBACK_START" >&2
  rm -f "$CONF"
  systemctl daemon-reload
  systemctl restart "$UNIT" || true
  echo "BROKERAGE_PRIVATE_RELEASE_ROLLBACK_COMPLETE" >&2
fi' EXIT
temp=$(mktemp "$DIR/.brokerage-premium-XXXXXXXX")
cat > "$temp" <<'EOF'
# Empire AI feature release: ONLY premium founder-led discovery intake.
# No changes to payment/binding order/drop-in configurations.
[Service]
Environment="EMPIRE_BROKERAGE_PREMIUM_PRIVATE_RELEASE=ON"
ExecStart=
ExecStart=/srv/empire_os/.venv/bin/python -m uvicorn empire_os.data_brokerage_premium_private_service:app --host 127.0.0.1 --port 8098 --workers 1
EOF
chmod 0644 "$temp"
mv -- "$temp" "$CONF"
systemctl daemon-reload
systemctl restart "$UNIT"

# A GET proves the internal route exists. Never submit synthetic buyer PII.
for attempt in 1 2 3 4 5 6 7 8; do
  if curl -fsS --max-time 4 http://127.0.0.1:8098/v1/brokerage/premium-discovery | "$PY" -c '
import json,sys
x=json.load(sys.stdin)
assert x["status"]=="UNPRICED_DISCOVERY_ONLY_NOT_PUBLICLY_PUBLISHED"
assert len(x["offers"])==2
assert not any(o.get("enquiry_enabled_in_production") is True or o.get("price_approved") is True for o in x["offers"])
' 2>/dev/null; then
    echo "PRIVATE_BROKERAGE_DISCOVERY_LIVE_LOOPBACK_GET_VERIFIED"
    trap - EXIT
    echo "NO_PAYMENTS_NO_OUTBOUND_NO_CRM_WRITES_BY_RELEASE"
    exit 0
  fi
  sleep 1
done
fail LIVE_PRIVATE_ROUTE_PROOF_FAILED
