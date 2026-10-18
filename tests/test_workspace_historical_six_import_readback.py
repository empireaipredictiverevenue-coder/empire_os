"""Trust-minimal post-import readback; zero CRM or outbound authority."""
import json
from copy import deepcopy

import pytest

from empire_os.workspace_solar_founder_review import project_workspace_review
from empire_os.workspace_solar_historical_status import _status_from_rows
from scripts.verify_workspace_historical_six_import_20261018 import (
    ReadbackHeld, verify, _read, HIST, BASE,
)
from tests.test_workspace_solar_historical_status import (
    manifest, rows,
)
from tests.test_workspace_solar_founder_review import NOW, snapshot


def sample():
    m=manifest()
    return (
        _status_from_rows(m,table_exists=True,rows=rows(m)),
        project_workspace_review(snapshot(),now=NOW),
    )


def test_all_six_originals_are_readback_proven_without_crm_promotion():
    hist,gmail=sample()
    result=verify(hist,gmail)
    assert result["status"]=="SIX_HISTORICAL_GMAIL_RECEIPTS_IN_EMPIREDB_VERIFIED"
    assert result["evidence_receipts_verified"]==6
    assert result["gmail_original_sends_verified"]==6
    assert result["canonical_outbound_intents_created"]==0
    assert result["historical_approvals_backfilled"]==0
    assert result["crm_records_created"]==0
    assert result["emails_sent"] is False
    assert result["database_writes"] is False
    assert "@" not in json.dumps(result)


@pytest.mark.parametrize("key,bad",[
    ("status","PRIVATE_CUSTODY_ONLY_DATABASE_SCHEMA_HELD"),
    ("database_historical_receipt_table_active",False),
    ("private_custody_receipts_verified",0),
    ("database_historical_receipts_verified",0),
    ("crm_handoff_authorized",True),
    ("canonical_outbound_intents_created",1),
    ("crm_records_created",1),
    ("outbound_sent",True),
    ("payment_executed",True),
    ("historical_approvals_backfilled",1),
])
def test_unverified_or_commercially_unsafe_report_is_held(key,bad):
    h,g=sample()
    h[key]=bad
    with pytest.raises(ReadbackHeld):
        verify(h,g)


@pytest.mark.parametrize("field,bad",[
    ("empiredb_historical_evidence_admitted",False),
    ("original_sent_receipt_custody_verified",False),
    ("canonical_sent_intent_created",True),
    ("crm_contact_bound",True),
    ("commercial_revenue_verified",True),
    ("historical_approval_verified",True),
    ("status","APPROVED_CUSTOMER"),
    ("company","FAKE_BRAND"),
])
def test_bad_individual_receipt_never_satisfies_aggregate(field,bad):
    h,g=sample()
    h["items"][0][field]=bad
    with pytest.raises(ReadbackHeld,match="UNVERIFIED_INDIVIDUAL_RECEIPT"):
        verify(h,g)


def test_duplicate_company_and_fake_gmail_cannot_claim_completion():
    h,g=sample()
    h["items"][1]["company"]=h["items"][0]["company"]
    with pytest.raises(ReadbackHeld):
        verify(h,g)
    h,g=sample()
    g["sent_anchors_verified"]=5
    with pytest.raises(ReadbackHeld):
        verify(h,g)


class FakeResponse:
    status=200
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self,size):return b'{"status":"OK"}'


def test_private_read_uses_exact_allowlisted_loopback_and_bounded_get():
    requests=[]
    def opener(req,*,timeout):
        requests.append((req.full_url,req.get_method(),timeout))
        return FakeResponse()
    assert _read(HIST,opener=opener)=={"status":"OK"}
    assert requests==[(BASE+HIST,"GET",9)]
    with pytest.raises(ReadbackHeld,match="SOURCE_NOT_ALLOWLISTED"):
        _read("/arbitrary",opener=opener)
