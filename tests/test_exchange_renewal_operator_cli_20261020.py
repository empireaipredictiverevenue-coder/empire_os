"""Private read-only Exchange renewal option cannot publish receipt PII."""
from datetime import datetime,timezone
from pathlib import Path
import json
import os
import subprocess
import sys

from tests.test_lead_exchange_live_inventory_20261019 import fixture
from tests.test_exchange_seat_renewal_lifecycle_v1_20261020 import (
    membership, paid,
)


def _run(snapshot:Path, private:Path|None=None):
    args=[sys.executable,"-B","-m",
          "scripts.review_exchange_self_serve_fulfilment_mrr_20261020",
          "--read-only","--snapshot",str(snapshot)]
    if private is not None:
        args+=["--private-renewal-cycles-file",str(private)]
    return subprocess.run(args,text=True,capture_output=True,check=False,timeout=25,
                          env={**os.environ,"PYTHONPATH":str(Path(__file__).resolve().parents[1])})


def _snapshot(tmp_path:Path)->Path:
    snap=fixture()
    snap["observed_at"]=datetime.now(timezone.utc).isoformat()
    p=tmp_path/"read_only_canonical_exchange_snapshot.json"
    p.write_text(json.dumps(snap))
    return p


def test_missing_private_finance_input_is_unknown_not_paid(tmp_path):
    r=_run(_snapshot(tmp_path))
    assert r.returncode==0, r.stderr
    x=json.loads(r.stdout)
    assert x["private_renewal_review"]["state"]=="NO_AUTHENTICATED_RENEWAL_OWNER_SOURCE_ATTACHED"
    assert x["private_renewal_review"]["recognized_mrr_cents"]==0
    assert x["subscription_activation_authorized"] is False
    assert x["lead_delivery_authorized"] is False


def test_private_0600_synthetic_input_shape_only_no_credential_leak(tmp_path):
    p=_snapshot(tmp_path)
    m=membership()
    m["buyer_private_email"]="secret-contact@example.test"
    m["do_not_copy_person_name"]="Customer Private Name"
    private=tmp_path/"finance_owner_private.json"
    private.write_text(json.dumps({"membership":m,"periods":[paid()]}))
    private.chmod(0o600)
    r=_run(p,private)
    assert r.returncode==0,r.stderr
    x=json.loads(r.stdout)
    assert x["private_renewal_review"]["state"]=="RENEWAL_REVIEW_NO_EXECUTION"
    assert x["private_renewal_review"]["entitlements_activated"]==0
    assert x["private_renewal_review"]["recognized_mrr_cents"]==0
    assert x["subscription_activation_authorized"] is False
    assert "secret-contact" not in r.stdout
    assert "Customer Private Name" not in r.stdout
    assert "44444444-4444" not in r.stdout


def test_unprotected_private_file_fails_closed_not_partially_read(tmp_path):
    p=_snapshot(tmp_path)
    private=tmp_path/"too_public_finance_receipts.json"
    private.write_text(json.dumps({"membership":membership(),"periods":[paid()]}))
    private.chmod(0o644)
    r=_run(p,private)
    assert r.returncode==2
    x=json.loads(r.stdout)
    assert x["state"]=="HOLD"
    assert x["recognized_mrr_cents"]==0
    assert x["lead_delivery_authorized"] is False


def test_untrusted_private_file_shape_held(tmp_path):
    p=_snapshot(tmp_path)
    private=tmp_path/"private_receipts.json"
    private.write_text(json.dumps({"random":"buyer email hidden"}))
    private.chmod(0o600)
    r=_run(p,private)
    assert r.returncode==2
    assert json.loads(r.stdout)["state"]=="HOLD"
