"""The existing two provider replies never become invented qualification/terms."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import pytest

from scripts.review_existing_lead_smart_inquirly_inbound_20261027 import (
    _load, review, REGISTRY, PULSE, main,
)

NOW=datetime(2026,10,27,17,tzinfo=timezone.utc)

def sources():
    return _load(REGISTRY),_load(PULSE)

def test_original_review_two_real_inbounds_and_no_new_actions(capsys):
    registry,pulse=sources()
    r=review(registry,pulse,now=NOW)
    assert r["status"]=="INBOUND_REQUIREMENTS_CLASSIFIED_NO_NEW_OUTBOUND"
    assert r["lead_smart"]["present_site_handoffs"]==0
    assert r["lead_smart"]["site_call_admission_enabled"] is False
    assert r["lead_smart"]["terms_fully_accepted"] is False
    assert r["lead_smart"]["verified_accepted_payable_calls"]==0
    assert r["lead_smart"]["original_routing_or_full_requirements_request_repeat"] is False
    assert r["inquirly"]["current_pilot_available"] is False
    assert r["inquirly"]["repeat_original_requirements_request"] is False
    assert r["email_sent"] is False
    assert r["canonical_crm_write_performed"] is False
    assert r["recorded_commercial_terms"] is False
    assert r["revenue_recognized"] is False
    assert main(["--read-only"])==0

def test_altered_inbound_disposition_does_not_inherit_previous_answer():
    r,p=sources()
    bad=deepcopy(r)
    next(x for x in bad["relationships"] if x.get("entity_key")=="inquirly.com")["reviewed_buyer_reply_disposition"]["status"]="PARTNER_APPROVED"
    with pytest.raises(ValueError,match="CANONICAL_PARTNER_DISPOSITION_CHANGED"):
        review(bad,p,now=NOW)

def test_unverified_terms_cannot_be_promoted_to_true():
    r,p=sources()
    bad=deepcopy(r)
    next(x for x in bad["relationships"] if x.get("entity_key")=="lead-smart")["partner_commercial_terms_verified"]=True
    with pytest.raises(ValueError,match="CANONICAL_PARTNER_DISPOSITION_CHANGED"):
        review(bad,p,now=NOW)

def test_live_pilot_switch_or_real_handoff_requires_fresh_review():
    r,p=sources()
    bad=deepcopy(p)
    bad["site_handoff_switch_enabled"]=True
    with pytest.raises(ValueError,match="LIVE_CALL_OR_PAYMENT_STATE_CHANGED"):
        review(r,bad,now=NOW)
    bad=deepcopy(p)
    bad["site_handoffs_recorded"]=1
    with pytest.raises(ValueError,match="LIVE_CALL_OR_PAYMENT_STATE_CHANGED"):
        review(r,bad,now=NOW)

def test_duplicate_existing_partner_identity_fails_closed():
    r,p=sources()
    bad=deepcopy(r)
    bad["relationships"].append(next(x for x in bad["relationships"] if x.get("entity_key")=="lead-smart"))
    with pytest.raises(ValueError,match="DUPLICATE_PARTNER_ROW"):
        review(bad,p,now=NOW)

def test_untrusted_schema_or_future_date_fails_closed():
    r,p=sources()
    bad=deepcopy(p);bad["campaign_id"]="OTHER"
    with pytest.raises(ValueError,match="WRONG_OR_UNTRUSTED"):
        review(r,bad,now=NOW)
    with pytest.raises(ValueError,match="AWARE_CLOCK_REQUIRED"):
        review(r,p,now=datetime(2026,10,27))
