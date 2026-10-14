"""Guarded direct BSC buyer status production release operator tests."""
from pathlib import Path
from unittest.mock import Mock
import json

import pytest

from scripts import deploy_direct_bsc_buyer_status_release as r


def test_no_args_and_unapproved_apply_never_write(capsys,monkeypatch):
    monkeypatch.setattr(r,"release",lambda:pytest.fail("would write"))
    assert r.main([])==0
    for args in (["--apply"],["--force"],["--apply","--approved-050-private-token-issuer-only"],
                 ["--apply",r.APPROVAL,"--again"]):
        assert r.main(args)==3
    assert "STAGED_NOT_APPLIED" in capsys.readouterr().out


def test_explicit_scope_no_payment_or_email_authority():
    script=Path(r.__file__).read_text()
    assert r.APPROVAL=="--approved-direct-bsc-buyer-status-release-only"
    assert "Environment=EMPIRE_DIRECT_BSC_BUYER_STATUS_RELEASE=ON" in r.DROPIN
    assert "LoadCredential=empire_direct_bsc_buyer_status_hmac.key" in r.DROPIN
    assert "LoadCredential=empire_direct_bsc_buyer_status.env" in r.DROPIN
    assert "EMPIRE_SELF_SERVE_PAYMENT_PROPOSAL_AUTHORIZED=ON" not in r.DROPIN
    assert "EMPIRE_SELF_SERVE_BINDING_ORDERS_AUTHORIZED=ON" not in r.DROPIN
    assert "BSC_TREASURY_ADDRESS=" not in r.DROPIN
    assert "ALTER ROLE " not in script
    assert "CREATE ROLE " not in script
    assert "INSERT INTO public." not in script
    assert "SMTP" not in r.DROPIN
    assert "SendMail" not in r.DROPIN


def test_chain_evidence_must_be_mainnet_and_canonical(monkeypatch):
    monkeypatch.setattr("empire_os.self_serve_payment_readiness.verify_checkout_bsc_chain",
                        lambda config:{"chain_verified":True,"chain_id":56,"token_decimals":18})
    assert r._chain_verified()["chain_verified"] is True
    monkeypatch.setattr("empire_os.self_serve_payment_readiness.verify_checkout_bsc_chain",
                        lambda config:{"chain_verified":True,"chain_id":97,"token_decimals":18})
    with pytest.raises(ValueError,match="chain"):
        r._chain_verified()


def test_status_probe_rejects_missing_or_non_denial_route(monkeypatch):
    class JsonResponse:
        def __init__(self,code,body):self.status=code;self.body=body
        def __enter__(self):return self
        def __exit__(self,*a):return False
        def read(self):return json.dumps(self.body).encode()
    from urllib.error import HTTPError
    def good(request,timeout):
        assert "/v1/checkout/payment-status" in request.full_url
        assert request.get_method()=="POST"
        assert b"order_id" not in request.data
        raise HTTPError(request.full_url,404,"",{},
            __import__("io").BytesIO(
                b'{"error":"payment_status_unavailable"}'))
    monkeypatch.setattr(r.urllib.request,"urlopen",good)
    r._status_probe()
    def wrong(request,timeout):
        raise HTTPError(request.full_url,404,"",{},
            __import__("io").BytesIO(b'{"detail":"Not Found"}'))
    monkeypatch.setattr(r.urllib.request,"urlopen",wrong)
    with pytest.raises(r.SafeReleaseHold) as caught:
        r._status_probe()
    assert caught.value.stage=="PRIVATE_STATUS_ROUTE_NOT_MOUNTED"


def test_release_does_not_rotate_existing_key_and_preserves_order_flags(monkeypatch):
    monkeypatch.setattr(r.os,"geteuid",lambda:0)
    monkeypatch.setattr(r,"_reviewed",lambda:None)
    monkeypatch.setattr(r,"_published_checkout_verified",lambda:None)
    monkeypatch.setattr(r,"_verify_unit_targets",lambda:None)
    monkeypatch.setattr(r,"_verify_login_file",lambda:None)
    monkeypatch.setattr(r,"checkout_financial_execution_held",lambda:None)
    monkeypatch.setattr(r,"_snapshot",lambda:("online","direct",True,True,False,False))
    monkeypatch.setattr(r,"_chain_verified",lambda:{"chain_verified":True})
    monkeypatch.setattr(r.KEY_FILE.__class__,"exists",lambda p:True)
    monkeypatch.setattr(r,"read_key",lambda:bytes(range(32)))
    monkeypatch.setattr(r,"install_key",lambda:pytest.fail("rotation"))
    monkeypatch.setattr(r,"_write_dropin",lambda:None)
    monkeypatch.setattr(r,"_wait_until_services_ready",lambda:None)
    monkeypatch.setattr(r,"_status_probe",lambda:None)
    actions=[]
    monkeypatch.setattr(r,"_run",lambda *args:actions.append(args))
    result=r.release()
    assert result["key"]=="EXISTING_KEY_VERIFIED"
    assert result["payment_execution"] is False
    assert result["order_gate_unchanged"] is True
    assert result["frontend_deployed"] is True
    assert actions==[
        ("systemctl","daemon-reload"),
        ("systemctl","restart","empire-self-serve-checkout.service"),
        ("systemctl","restart","empire-public-gateway.service"),
    ]


def test_operator_on_failure_never_prints_secrets(capsys,monkeypatch):
    monkeypatch.setattr(r,"release",lambda:(_ for _ in ()).throw(RuntimeError("private=abc")))
    assert r.main(["--apply",r.APPROVAL])==4
    output=capsys.readouterr().out
    assert "abc" not in output
    assert "HELD_RELEASE_OR_ROLLBACK_NEEDS_READBACK" in output




def test_release_waits_for_real_http_readiness_without_restarting(monkeypatch):
    called=[]
    def health():
        called.append("health")
        if len(called)<3:
            raise ConnectionRefusedError("startup not yet listening")
        return {"status":"online"}
    class Response:
        status=200
        def __enter__(self):return self
        def __exit__(self,*args):return False
    monkeypatch.setattr(r,"_health",health)
    monkeypatch.setattr(r.urllib.request,"urlopen",
                        lambda request,timeout:Response())
    r._wait_until_services_ready(seconds=2.0)
    assert len(called)==3


def test_release_readiness_fails_closed_at_bounded_deadline(monkeypatch):
    monkeypatch.setattr(r,"_health",
        lambda:(_ for _ in ()).throw(ConnectionRefusedError("not ready")))
    with pytest.raises(ValueError,match="HTTP-ready"):
        r._wait_until_services_ready(seconds=0.0)


def test_public_gateway_must_return_http_200_before_release_checks(monkeypatch):
    monkeypatch.setattr(r,"_health",lambda:{"status":"online"})
    class Response:
        status=503
        def __enter__(self):return self
        def __exit__(self,*args):return False
    monkeypatch.setattr(r.urllib.request,"urlopen",
                        lambda request,timeout:Response())
    with pytest.raises(ValueError,match="HTTP-ready"):
        r._wait_until_services_ready(seconds=0.0)

def test_targeted_git_paths_cover_checkout_gateway_and_status_and_operator():
    assert {"empire_os/public_gateway.py","empire_os/self_serve_checkout_api.py",
            "scripts/deploy_direct_bsc_buyer_status_release.py",
            "empire_os/direct_bsc_buyer_receipt_bridge.py"}.issubset(set(r.REVIEW_FILES))


def test_release_requires_the_verified_published_checkout_page(monkeypatch,tmp_path):
    from hashlib import sha256
    pages=tmp_path/"apps/empire-public-site/out"
    manifests=tmp_path/"docs/commercial"
    pages.mkdir(parents=True)
    manifests.mkdir(parents=True)
    page=pages/"buy.html"
    page.write_bytes(b"buyer-page-reviewed")
    expected=sha256(page.read_bytes()).hexdigest()
    (manifests/"DIRECT_BSC_BUY_UI_STATIC_EXPORT_MANIFEST_20261013.json").write_text(
        json.dumps({"buy_sha256":expected,"assets":[]})
    )
    monkeypatch.setattr(r,"ROOT",tmp_path)
    r._published_checkout_verified()
    page.write_bytes(b"buyer-page-unreviewed")
    with pytest.raises(ValueError,match="not verified"):
        r._published_checkout_verified()


def test_private_503_status_returns_redacted_runtime_held(monkeypatch):
    from urllib.error import HTTPError
    from io import BytesIO
    def held(request,timeout):
        raise HTTPError(request.full_url,503,"",{},
            BytesIO(b'{"error":"buyer_status_unavailable"}'))
    monkeypatch.setattr(r.urllib.request,"urlopen",held)
    with pytest.raises(r.SafeReleaseHold) as caught:
        r._status_probe()
    assert caught.value.stage=="PRIVATE_STATUS_ROUTE_HELD_BY_RUNTIME"


def test_public_generic_404_reports_public_not_mounted_after_private_success(monkeypatch):
    from urllib.error import HTTPError
    from io import BytesIO
    touched=[]
    def response(request,timeout):
        local=":8098" in request.full_url
        touched.append("PRIVATE" if local else "PUBLIC")
        body=(b'{"error":"payment_status_unavailable"}' if local
              else b'{"detail":"Not Found"}')
        raise HTTPError(request.full_url,404,"",{},BytesIO(body))
    monkeypatch.setattr(r.urllib.request,"urlopen",response)
    with pytest.raises(r.SafeReleaseHold) as caught:
        r._status_probe()
    assert caught.value.stage=="PUBLIC_STATUS_ROUTE_NOT_MOUNTED"
    assert touched==["PRIVATE","PUBLIC"]


def test_stage_redaction_does_not_disclose_exception_messages(capsys,monkeypatch):
    monkeypatch.setattr(r,"release",lambda:(
        _ for _ in ()).throw(r.SafeReleaseHold("PRIVATE_STATUS_ROUTE_NOT_MOUNTED_ROLLBACK_OK")))
    assert r.main(["--apply",r.APPROVAL])==4
    result=__import__("json").loads(capsys.readouterr().out)
    assert result["release_failure_stage"]=="PRIVATE_STATUS_ROUTE_NOT_MOUNTED_ROLLBACK_OK"
    assert result["no_secrets_printed"] is True
    assert "postgresql://" not in str(result)
