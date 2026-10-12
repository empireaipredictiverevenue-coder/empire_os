"""The public wallet signer page is offline and cannot spend funds."""
from __future__ import annotations
import json
from pathlib import Path
import pytest

from scripts.render_bsc_treasury_proof_page import render, EXPECTED_ADDRESS, TOKEN

TEMPLATE=Path(__file__).resolve().parents[1]/"apps/empire-public-site/treasury-proof-template.html"

def challenge(p:Path):
    data={
      "schema_version":"empire.bsc-treasury-control-challenge.v1",
      "candidate_wallet":EXPECTED_ADDRESS,
      "network_chain_id":56,
      "nonce":"0x"+"a"*48,
      "issued_at":"2026-10-12T09:00:00Z",
      "expires_at":"2026-10-14T09:00:00Z",
      "message":"Empire AI / EmpireOS — BSC Treasury Control Verification\nNo transactions, token approvals",
      "actual_funds_moved":False,
      "production_payment_activation":False,
    }
    p.write_text(json.dumps(data))
    p.chmod(0o600)
    return data

def test_public_signing_page_embeds_only_challenge_not_secrets(tmp_path):
    p=tmp_path/"challenge.json"; challenge(p)
    out=tmp_path/"treasury-proof.html"
    result=render(TEMPLATE,p,out)
    assert result["requests_funds"] is False
    assert result["uploads_signature"] is False
    html=out.read_text()
    assert "method:\"personal_sign\"" in html
    assert "method:\"eth_requestAccounts\"" in html
    assert "eth_sendTransaction" not in html and "fetch(" not in html
    assert "<form" not in html and "XMLHttpRequest" not in html
    assert TOKEN not in html
    assert EXPECTED_ADDRESS in html
    assert "No transactions, token approvals" in html
    assert out.stat().st_mode & 0o777==0o644

def test_renderer_will_not_overwrite_existing_signed_page(tmp_path):
    p=tmp_path/"challenge.json"; challenge(p)
    out=tmp_path/"treasury-proof.html"
    out.write_text("previous customer-facing proof")
    with pytest.raises(FileExistsError):
        render(TEMPLATE,p,out)
    assert out.read_text()=="previous customer-facing proof"

@pytest.mark.parametrize("field,value",[
 ("candidate_wallet","0x"+"1"*40),
 ("network_chain_id",1),
 ("schema_version","other"),
 ("actual_funds_moved",True),
 ("production_payment_activation",True),
])
def test_untrusted_chain_wallet_and_authority_challenge_rejected(tmp_path,field,value):
    p=tmp_path/"challenge.json"; obj=challenge(p); obj[field]=value
    p.write_text(json.dumps(obj))
    with pytest.raises(ValueError,match="untrusted wallet challenge"):
        render(TEMPLATE,p,tmp_path/"treasury-proof.html")

def test_challenge_file_requires_private_permissions(tmp_path):
    p=tmp_path/"challenge.json"; challenge(p)
    p.chmod(0o644)
    with pytest.raises(ValueError,match="private challenge"):
        render(TEMPLATE,p,tmp_path/"treasury-proof.html")
