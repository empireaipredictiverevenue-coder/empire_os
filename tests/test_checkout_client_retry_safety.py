"""Browser-order retry idempotency: real JS behavior plus source contract."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "apps/empire-public-site/src/lib/checkout-order-attempt.ts"
PAGE = ROOT / "apps/empire-public-site/src/app/buy/page.tsx"


def test_checkout_page_reuses_ephemeral_request_key_and_never_downgrades_entropy():
    source = PAGE.read_text(encoding="utf8")
    assert "reuseCheckoutOrderAttempt(" in source
    assert "const orderAttemptRef = useRef<CheckoutOrderAttempt | null>(null)" in source
    assert "orderAttemptRef.current = attempt;" in source
    assert "idempotency_key: attempt.idempotencyKey" in source
    assert "globalThis.crypto.randomUUID()" in source
    assert "secure_checkout_key_unavailable" in source
    assert "Math.random()" not in source
    assert "sessionStorage" not in source
    assert "localStorage" not in source
    assert 'fetch("/v1/checkout/orders"' in source


@pytest.mark.skipif(shutil.which("node") is None, reason="Node not available")
def test_same_order_retry_reuses_one_real_javascript_key_no_order_clone():
    script = '''
import assert from "node:assert/strict";
import { reuseCheckoutOrderAttempt as reuse } from "%s";
const base = {
  product_code:"competitor_search_gap", amount_cents:19900,
  business_name:"Example Ltd", email:"owner@example.com",
  target_domain:"example.com", payer_wallet:"0x" + "1".repeat(40),
  terms_accepted:true,
};
let sequence = 0;
const next = () => "valid-checkout-"+(++sequence);
const a = reuse(null,base,next);
const afterTimeout = reuse(a,{...base},next);
assert.strictEqual(afterTimeout, a);
assert.strictEqual(afterTimeout.idempotencyKey, a.idempotencyKey);
assert.strictEqual(sequence,1);
const differentProduct = reuse(a,{...base,product_code:"technical_search_audit"},next);
const differentPrice = reuse(a,{...base,amount_cents:29900},next);
const differentWallet = reuse(a,{...base,payer_wallet:"0x" + "2".repeat(40)},next);
const differentBuyer = reuse(a,{...base,email:"other@example.com"},next);
const differentConsent = reuse(a,{...base,terms_accepted:false},next);
for (const r of [differentProduct,differentPrice,differentWallet,differentBuyer,differentConsent]) {
  assert.notEqual(r.idempotencyKey, a.idempotencyKey);
}
assert.strictEqual(sequence,6);
const noEntropy = () => {throw new Error("secure_checkout_key_unavailable");};
assert.strictEqual(reuse(a,base,noEntropy),a);
assert.throws(()=>reuse(null,base,noEntropy),/secure_checkout_key_unavailable/);
assert.throws(()=>reuse(null,base,()=>""),/secure_checkout_key_unavailable/);
assert.throws(()=>reuse(null,base,()=>"bad key !"),/secure_checkout_key_unavailable/);
console.log("CHECKOUT_RETRY_REAL_JS=PASS");
''' % HELPER.resolve().as_uri()
    result = subprocess.run(
        ["node", "--disable-warning=ExperimentalWarning", "--experimental-strip-types",
         "--input-type=module", "-e", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "CHECKOUT_RETRY_REAL_JS=PASS" in result.stdout
