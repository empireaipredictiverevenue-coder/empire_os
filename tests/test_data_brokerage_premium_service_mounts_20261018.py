"""Actual HTTP route checks against isolated uvicorn wrapper imports.

No real CRM, buyer, email, production HTTP, checkout state or payment.
"""
from __future__ import annotations
import os
import subprocess
import sys
import json

def probe(module,flags=None):
    env=os.environ.copy()
    for key in (
        "EMPIRE_BROKERAGE_PREMIUM_PRIVATE_RELEASE",
        "EMPIRE_BROKERAGE_PREMIUM_PUBLIC_RELEASE",
        "EMPIRE_BROKERAGE_PREMIUM_PRIVATE_VERIFIED",
        "EMPIRE_BROKERAGE_PREMIUM_ASTRA_QA",
    ):
        env.pop(key,None)
    env.update(flags or {})
    code=(
        "import json;"
        "from fastapi.testclient import TestClient;"
        "from "+module+" import app;"
        "client=TestClient(app);"
        "print(json.dumps({"
        "'premium':client.get('/v1/brokerage/premium-discovery').status_code,"
        "'public':client.get('/v1/checkout/brokerage/premium-discovery').status_code,"
        "'private_blocked':client.post('/v1/brokerage/premium-discovery').status_code,"
        "'public_blocked':client.post('/v1/checkout/brokerage/premium-discovery').status_code,"
        "'original_private':client.get('/v1/commercial/offers').status_code,"
        "'original_public':client.get('/v1/checkout/commercial/offers').status_code"
        "}))"
    )
    proc=subprocess.run(
        [sys.executable,"-B","-c",code],env=env,
        capture_output=True,text=True,timeout=25,
    )
    return proc

def outcome(r):
    assert r.returncode==0,r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])

def test_both_wrapper_apps_preserve_original_api_when_flags_absent():
    pub=outcome(probe("empire_os.data_brokerage_premium_public_service"))
    private=outcome(probe("empire_os.data_brokerage_premium_private_service"))
    assert pub["public"]==404
    assert private["premium"]==404
    assert pub["original_public"]==200
    assert private["original_private"]==200

def test_checkout_private_route_requires_flag_and_enforces_origins():
    p=outcome(probe("empire_os.data_brokerage_premium_private_service",{
        "EMPIRE_BROKERAGE_PREMIUM_PRIVATE_RELEASE":"ON",
    }))
    assert p["premium"]==200
    assert p["private_blocked"]==403
    assert p["original_private"]==200

def test_public_requires_independent_live_private_and_astra_facts():
    for env in (
        {"EMPIRE_BROKERAGE_PREMIUM_PUBLIC_RELEASE":"ON"},
        {"EMPIRE_BROKERAGE_PREMIUM_PUBLIC_RELEASE":"ON",
         "EMPIRE_BROKERAGE_PREMIUM_PRIVATE_VERIFIED":"ON"},
        {"EMPIRE_BROKERAGE_PREMIUM_PUBLIC_RELEASE":"ON",
         "EMPIRE_BROKERAGE_PREMIUM_ASTRA_QA":"ON"},
    ):
        r=probe("empire_os.data_brokerage_premium_public_service",env)
        assert r.returncode!=0
        assert "PREMIUM_PUBLIC_ROUTE_RELEASE_AUTHORITY_HOLD" in r.stderr

def test_premium_public_route_reachable_only_when_all_flags():
    p=outcome(probe("empire_os.data_brokerage_premium_public_service",{
        "EMPIRE_BROKERAGE_PREMIUM_PUBLIC_RELEASE":"ON",
        "EMPIRE_BROKERAGE_PREMIUM_PRIVATE_VERIFIED":"ON",
        "EMPIRE_BROKERAGE_PREMIUM_ASTRA_QA":"ON",
    }))
    assert p["public"]==200
    assert p["public_blocked"]==403
    assert p["original_public"]==200

def test_no_live_prospect_ingest_from_route_introspection():
    r=probe("empire_os.data_brokerage_premium_private_service",{
        "EMPIRE_BROKERAGE_PREMIUM_PRIVATE_RELEASE":"ON"
    })
    p=outcome(r)
    assert p["private_blocked"]==403
    assert "commercial_enquiry_recorded" not in r.stdout
