"""Opt-in localhost browser acceptance across both original review branches.

Uses real original login signing/verifying, signed export, V5, Founder service,
Next routes and React page. Only password/membership/source stores are fixtures.
Never connects to production services or writes business records.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import threading
import time

import pytest


def test_original_login_signed_evidence_v5_founder_next_react(tmp_path):
    root = os.environ.get("EMPIRE_TEST_FRONTEND_ROOT")
    browser_module = os.environ.get("EMPIRE_TEST_PUPPETEER_PATH")
    if not root or not browser_module:
        pytest.skip("requires explicitly built frontend and isolated browser dependency")
    import uvicorn
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from empire_os.founder_dashboard_service import build_founder_dashboard_service
    from empire_os.predictive_revenue_company_timeline_v44 import build_signed_company_review_router
    from empire_os.revenue_crm_first_party_login import PostgresCrmPasswordLogin, create_crm_login_router
    from empire_os.saas_scale import TenantMembership
    from test_predictive_revenue_authorized_company_bridge import inputs, file_loader
    from test_predictive_revenue_company_timeline_v44 import signed_export_fixture, COMPANY, NOW
    from test_revenue_crm_signed_auth import A

    bundle = inputs()
    payload, manifest, _, trusted, sign = signed_export_fixture()
    manifest["tenant_scope"] = trusted["tenant_scope"] = A
    bundle.update(payload=payload, signed_manifest=manifest, trusted_source=trusted, signature_b64=sign(manifest))
    for name in ("signal_rows", "issued_forecast_rows"):
        for row in bundle[name]: row["tenant_scope"] = A
    _, config, source = file_loader(tmp_path, bundle)
    before = {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    key = Ed25519PrivateKey.generate()
    membership_reads = []
    def member(user, tenant):
        membership_reads.append((user, tenant))
        return TenantMembership(A, user, "viewer") if tenant == A and user == "fixture:user" else None
    class FixturePasswordStore(PostgresCrmPasswordLogin):
        def __init__(self): pass
        def authenticate(self, email, password):
            return "fixture:user" if email == "fixture@example.invalid" and password == "fixture-password-only" else None
    app = build_founder_dashboard_service(company_review_router_factory=lambda: build_signed_company_review_router(
        trusted_public_keys={"fixture-key": key.public_key()}, load_membership=member,
        authorize_company_review=lambda member, **scope: scope == {"company_scope": COMPANY, "source_id": source, "purpose": "PREDICTIVE_REVENUE_OBSERVE"},
        source_bindings={(A, COMPANY, source): config}, now=lambda: NOW))
    app.include_router(create_crm_login_router(password_login=FixturePasswordStore(), load_membership=member,
        load_invitation_membership=lambda *a: None, signing_key=key, key_id="fixture-key", now=lambda: int(NOW.timestamp())))
    sock = socket.socket(); sock.bind(("127.0.0.1", 0)); backend_port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True); thread.start()
    with socket.socket() as free:
        free.bind(("127.0.0.1", 0)); port = free.getsockname()[1]
    frontend = Path(root).resolve()
    assert (frontend / ".next/BUILD_ID").is_file()
    env = {**os.environ, "EMPIRE_API_BASE_URL": f"http://127.0.0.1:{backend_port}",
        "EMPIRE_CRM_API_BASE_URL": f"http://127.0.0.1:{backend_port}", "EMPIRE_CONSOLE_ORIGIN": f"http://127.0.0.1:{port}", "NEXT_TELEMETRY_DISABLED": "1"}
    child = subprocess.Popen(["node", str(frontend / "node_modules/next/dist/bin/next"), "start", "--hostname", "127.0.0.1", "--port", str(port)], cwd=frontend, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        import urllib.request
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/predictive-revenue", timeout=1).close(); break
            except OSError: time.sleep(.1)
        settings = json.dumps({"url": f"http://127.0.0.1:{port}/predictive-revenue", "tenant": A, "company": COMPANY, "source": source, "forecast": bundle["issued_forecast_rows"][0]["forecast_id"]})
        javascript = r"""
const assert = require('node:assert/strict');
const puppeteer = require(process.env.EMPIRE_TEST_PUPPETEER_PATH);
(async () => {
 const browser = await puppeteer.launch({headless: true, args: ['--no-sandbox', '--disable-setuid-sandbox']});
 try {
  const page = await browser.newPage(); await page.goto(settings.url, {waitUntil: 'networkidle0'});
  await page.type('[name="email"]', 'fixture@example.invalid');
  await page.type('[name="password"]', 'fixture-password-only');
  await page.type('[name="tenant_id"]', settings.tenant);
  await page.click('form button'); await page.waitForSelector('[name="company_scope"]');
  await page.type('[name="company_scope"]', settings.company); await page.type('[name="source_id"]', settings.source);
  const clickReview = () => page.evaluate(() => [...document.querySelectorAll('button')].find(b => b.textContent === 'Review permitted evidence').click());
  await clickReview(); await page.waitForSelector('[data-testid="private-company-result"]');
  assert.ok((await page.content()).includes(settings.forecast));
  assert.ok((await page.content()).includes('SIGNED_EXPORT_READ_ONLY_HOLD_UNVERIFIED_BUSINESS_HISTORY'));
  await clickReview(); await page.waitForSelector('[data-testid="private-company-result"]');
  assert.ok((await page.content()).includes(settings.forecast));
  await page.$eval('[name="source_id"]', e => e.value = 'wrong-source');
  await clickReview(); await page.waitForFunction(() => document.body.textContent.includes('not authorised'));
  assert.equal(await page.$('[data-testid="private-company-result"]'), null);
  await page.evaluate(() => [...document.querySelectorAll('button')].find(b => b.textContent === 'Sign out').click());
  await page.waitForSelector('[name="email"]');
  assert.deepEqual(await page.evaluate(() => [localStorage.length, sessionStorage.length, document.cookie]), [0,0,'']);
  console.log('ORIGINAL_SIGNED_LOGIN_TO_V5_TO_REACT_FIXTURE_SLICE_PASS');
 } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
"""
        result = subprocess.run(["node", "-e", "const settings = " + settings + ";\n" + javascript], env=env, text=True, capture_output=True, timeout=90)
        assert result.returncode == 0, result.stderr
        assert "ORIGINAL_SIGNED_LOGIN_TO_V5_TO_REACT_FIXTURE_SLICE_PASS" in result.stdout
        assert len(membership_reads) >= 4
        assert {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == before
    finally:
        child.terminate()
        try: child.wait(timeout=10)
        except subprocess.TimeoutExpired: child.kill(); child.wait()
        server.should_exit = True; thread.join(timeout=10); sock.close()
