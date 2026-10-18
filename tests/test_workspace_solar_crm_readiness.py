"""One existing commercial loop, independently validated, no fake CRM."""
from copy import deepcopy
import json

import pytest

from empire_os.workspace_solar_crm_readiness import (
    CRMReadinessHeld,combine_six_company_crm_readiness,
)
from empire_os.workspace_solar_canonical_intent_review import _parse_counts
from empire_os.workspace_solar_historical_status import _status_from_rows
from empire_os.workspace_solar_founder_review import project_workspace_review
from scripts.review_workspace_solar_crm_readiness_20261018 import PATHS,HOST
from tests.test_workspace_solar_canonical_intent_review import rows as canonical_rows
from tests.test_workspace_solar_historical_status import manifest,rows as historical_rows
from tests.test_workspace_solar_founder_review import NOW,snapshot


def evidence():
    m=manifest()
    historical=_status_from_rows(m,table_exists=True,rows=historical_rows(m))
    canonical=_parse_counts(canonical_rows(),recipient_rows=canonical_rows())
    gmail=project_workspace_review(snapshot(),now=NOW)
    return historical,canonical,gmail


def test_six_real_historical_sends_are_unbound_and_not_buyer_conversations():
    report=combine_six_company_crm_readiness(*evidence())
    assert report["status"]=="SIX_COMPANY_HISTORICAL_TO_CRM_GAP_REGISTER_READ_ONLY"
    assert report["companies_checked"]==6
    assert report["historical_receipts_verified_in_empiredb"]==6
    assert report["inbound_provider_header_candidates"]==0
    assert report["founder_crm_handoff_authorized"] is False
    assert report["crm_records_created"]==0
    assert report["database_writes"] is False
    assert all(
        x["canonical_intent_linkage"]=="NO_CANONICAL_INTENT_VISIBLE_TO_READER"
        and x["inbound_next_review_action"]=="WAIT_FOR_GENUINE_BUYER_REPLY"
        and x["crm_record_created"] is False
        for x in report["items"]
    )
    assert "@" not in json.dumps(report)
    assert "gmail_message_id" not in json.dumps(report)


@pytest.mark.parametrize("source,field,new",[
    (0,"database_historical_receipts_verified",5),
    (0,"crm_handoff_authorized",True),
    (0,"crm_records_created",1),
    (1,"exact_recipient_scan_complete",False),
    (1,"crm_mutation",True),
    (1,"founder_crm_delivery_verified",True),
    (2,"sent_anchors_verified",5),
    (2,"crm_identity_and_tenant_unverified",False),
    (2,"inbound_header_candidate_count",1),
    (2,"outbound_sent",True),
])
def test_source_uncertainty_or_forged_authority_fails_closed(source,field,new):
    docs=list(evidence())
    docs[source][field]=new
    with pytest.raises(CRMReadinessHeld):
        combine_six_company_crm_readiness(*docs)


@pytest.mark.parametrize("source,key,value",[
    (0,"empiredb_historical_evidence_admitted",False),
    (0,"historical_approval_verified",True),
    (0,"crm_contact_bound",True),
    (1,"historical_send_reconciliation_automatically_authorized",True),
    (1,"tenant_identity_verified",True),
    (1,"next_founder_review_action","FAKE_AUTO_APPROVAL"),
    (2,"sent_verified",False),
    (2,"tenant_and_contact_binding_verified",True),
])
def test_forged_company_level_authority_rejected(source,key,value):
    docs=list(evidence())
    docs[source]["items"][0][key]=value
    with pytest.raises(CRMReadinessHeld):
        combine_six_company_crm_readiness(*docs)


def test_duplicate_company_does_not_pass_aggregate_counts():
    docs=list(evidence())
    docs[0]["items"][1]["company"]=docs[0]["items"][0]["company"]
    with pytest.raises(CRMReadinessHeld):
        combine_six_company_crm_readiness(*docs)


def test_canonical_recipient_only_never_authorises_crm():
    history,canonical,gmail=evidence()
    for c in canonical["items"]:
        c["canonical_same_recipient_intents_visible"]=1
        c["next_founder_review_action"]="REVIEW_POTENTIAL_UNLINKED_EXACT_RECIPIENT_RECORDS"
    report=combine_six_company_crm_readiness(history,canonical,gmail)
    assert report["crm_records_created"]==0
    assert all(
        x["canonical_intent_linkage"]=="CANONICAL_RECONCILIATION_REQUIRED"
        and x["crm_handoff_status"]=="NOT_AUTHORISED_REQUIRES_CONTACT_TENANT_AND_REPLY_PROOF"
        for x in report["items"]
    )


def test_cli_routes_are_exact_private_get_endpoints():
    assert HOST=="http://127.0.0.1:8766"
    assert set(PATHS)=={"history","canonical","gmail"}
    assert len(set(PATHS.values()))==3
    assert all(p.startswith("/v1/founder-mailbox/") for p in PATHS.values())
