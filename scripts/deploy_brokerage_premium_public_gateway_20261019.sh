#!/usr/bin/env bash
# Empire AI: future founder-controlled unpriced premium public API release.
# Does NOT overwrite or regenerate ASTRA commercial page assets.
# Will not run until the real private GET and served frontend JS are verified.
set -euo pipefail
ROOT=/srv/empire_os
PY="$ROOT/.venv/bin/python"
UNIT=empire-public-gateway.service
DIR="/etc/systemd/system/$UNIT.d"
CONF="$DIR/95-empire-brokerage-premium-public.conf"
PRIVATE=http://127.0.0.1:8098/v1/brokerage/premium-discovery
PUBLIC=http://127.0.0.1/v1/checkout/brokerage/premium-discovery

fail() { echo "BROKERAGE_PUBLIC_RELEASE_HOLD=$1" >&2; exit 2; }

case "${1:-}" in
  --source-preflight|--preflight|--apply-founder-approved-unpriced-public-enquiry) ;;
  *) fail EXACT_RELEASE_FLAG_REQUIRED ;;
esac

cd "$ROOT"
[[ -f empire_os/data_brokerage_premium_public_service.py ]] || fail PUBLIC_SERVICE_WRAPPER_MISSING
[[ -f empire_os/data_brokerage_premium_private_service.py ]] || fail PRIVATE_SERVICE_WRAPPER_MISSING
[[ -f empire_os/data_brokerage_premium_gateway_adapter.py ]] || fail GATEWAY_ADAPTER_MISSING
[[ ! -e "$CONF" ]] || fail EXISTING_PREMIUM_PUBLIC_DROPIN_REQUIRES_AUDIT

systemctl is-active --quiet "$UNIT" || fail ORIGINAL_GATEWAY_NOT_ACTIVE
systemctl is-active --quiet empire-self-serve-checkout.service || fail ORIGINAL_CHECKOUT_NOT_ACTIVE
systemctl show -p ExecStart --value "$UNIT" | grep -Fq 'empire_os.public_gateway:app' || fail GATEWAY_ENTRYPOINT_CHANGED
[[ -z "$(git status --porcelain -- empire_os/data_brokerage_premium_public_service.py empire_os/data_brokerage_premium_private_service.py empire_os/data_brokerage_premium_gateway_adapter.py)" ]] || fail UNCOMMITTED_RELEASE_ADAPTER

"$PY" -B -m pytest -q   tests/test_data_brokerage_premium_gateway_adapter_20261018.py   tests/test_data_brokerage_premium_service_mounts_20261018.py   tests/test_data_brokerage_premium_enquiry_20261018.py   >/dev/null || fail PREMIUM_ADAPTER_REGRESSION

# Verify original nonbinding entry offer survives the release candidate.
curl -fsS --max-time 4 http://127.0.0.1/v1/checkout/commercial/offers | "$PY" -c '
import json,sys
v=json.load(sys.stdin)
assert v["status"]=="FOUNDER_LED_ENQUIRY_AVAILABLE"
assert any(o.get("product_code")=="competitor_search_gap" for o in v["offers"])
' || fail ORIGINAL_199_OFFER_UNAVAILABLE

echo "BROKERAGE_PUBLIC_SOURCE_PREFLIGHT_PASS (no service/site changes)"

[[ "${1:-}" != "--source-preflight" ]] || exit 0

# The original live premium private endpoint must be running, not merely in
# source or in an isolated TestClient fixture.
curl -fsS --max-time 4 "$PRIVATE" | "$PY" -c '
import json,sys
r=json.load(sys.stdin)
assert r["status"]=="UNPRICED_DISCOVERY_ONLY_NOT_PUBLICLY_PUBLISHED"
assert len(r["offers"])==2
assert {x["product_code"] for x in r["offers"]}=={"brokerage_agency_discovery","brokerage_enterprise_discovery"}
assert not any(x.get("price_approved") for x in r["offers"])
' || fail LIVE_PRIVATE_API_NOT_VERIFIED

# The specific *currently served commercial page* must reference the
# corresponding compiled page JS, not the old 2026-10-18 HTML; no rebuild here.
"$PY" - <<'PY' || exit 2
from pathlib import Path
from html.parser import HTMLParser
root=Path("/srv/empire_os/apps/empire-public-site/out")
html=root/"commercial.html"
class Extract(HTMLParser):
    def __init__(self):
        super().__init__();self.assets=[]
    def handle_starttag(self,tag,attrs):
        if tag=="script":
            src=dict(attrs).get("src")
            if isinstance(src,str) and src.startswith("/_next/static/chunks/app/commercial/page-"):
                self.assets.append(src)
if not html.is_file() or html.stat().st_size>2_000_000:
    raise SystemExit("HOLD_PUBLISHED_COMMERCIAL_HTML_UNAVAILABLE")
parser=Extract();parser.feed(html.read_text(encoding="utf8"))
if len(parser.assets)!=1:
    raise SystemExit("HOLD_COMMERCIAL_SITE_PAGE_BUNDLE_NOT_UNAMBIGUOUS")
url=parser.assets[0]
path=(root/url.lstrip("/")).resolve()
if root.resolve() not in path.parents or not path.is_file() or path.stat().st_size>8_000_000:
    raise SystemExit("HOLD_CURRENT_LIVE_PAGE_JS_NOT_VERIFIED")
js=path.read_bytes()
if b"/v1/checkout/brokerage/premium-discovery" not in js or b"Request an intelligence scope" not in js:
    raise SystemExit("HOLD_ASTRA_PREMIUM_COMPONENT_ABSENT_FROM_LIVE_PAGE_JS")
print("BROKERAGE_LIVE_COMMERCIAL_PAGE_BUNDLE_CONTAINS_PREMIUM_COMPONENT")
PY

# Never accidentally incorporate concurrently edited shared source on restart.
[[ -z "$(git status --porcelain -- empire_os/public_gateway.py empire_os/self_serve_checkout_api.py)" ]] || fail UNCOMMITTED_OTHER_AGENT_GATEWAY_OR_CHECKOUT_EDITS

echo "BROKERAGE_PREMIUM_PUBLIC_READINESS_PREFLIGHT_PASS"
[[ "${1:-}" != "--preflight" ]] || exit 0
[[ "${EUID:-$(id -u)}" == 0 ]] || fail ROOT_REQUIRED_FOR_SYSTEMD_DROPIN

mkdir -p "$DIR"
trap 'st=$?; if [[ "$st" -ne 0 && -f "$CONF" ]]; then
  echo "BROKERAGE_PREMIUM_PUBLIC_ROLLBACK" >&2
  rm -f "$CONF"
  systemctl daemon-reload
  systemctl restart "$UNIT" || true
fi' EXIT
tmp=$(mktemp "$DIR/.brokerage-premium-public-XXXXXXXX")
cat > "$tmp" <<'EOF'
# Empire AI source-reviewed premium B2B enquiries only; no financial change
[Service]
Environment="EMPIRE_BROKERAGE_PREMIUM_PUBLIC_RELEASE=ON"
Environment="EMPIRE_BROKERAGE_PREMIUM_PRIVATE_VERIFIED=ON"
Environment="EMPIRE_BROKERAGE_PREMIUM_ASTRA_QA=ON"
ExecStart=
ExecStart=/srv/empire_os/.venv/bin/python -m uvicorn empire_os.data_brokerage_premium_public_service:app --host 127.0.0.1 --port 80 --workers 1
EOF
chmod 0644 "$tmp"
mv -- "$tmp" "$CONF"
systemctl daemon-reload
systemctl restart "$UNIT"

for attempt in 1 2 3 4 5 6 7 8; do
    if curl -fsS --max-time 4 "$PUBLIC" | "$PY" -c '
import json,sys
v=json.load(sys.stdin)
assert v["status"]=="UNPRICED_DISCOVERY_CHOICES_NONBINDING"
assert v["count"]==2
assert not v["payment_authorized"] and not v["binding_terms_ready"]
assert {x["product_code"] for x in v["offers"]}=={"brokerage_agency_discovery","brokerage_enterprise_discovery"}
' 2>/dev/null; then
       echo "BROKERAGE_PUBLIC_PREMIUM_GET_VERIFIED"
       trap - EXIT
       echo "NO_SYNTHETIC_BUYERS_NO_PAYMENTS_NO_OUTBOUND"
       exit 0
    fi
    sleep 1
done
fail LIVE_PUBLIC_GET_VERIFICATION_FAILED
