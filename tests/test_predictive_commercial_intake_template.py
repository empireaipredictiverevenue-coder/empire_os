"""Unfilled commercial intake template - no invented buyer/market/payment."""
import json
import subprocess
import sys
from datetime import datetime,timezone
import pytest

from scripts.print_predictive_commercial_intake_template_20261020 import (
    commercial_intake_template,
)
from empire_os.predictive_commercial_requirements import (
    INPUT_FIELDS,review_commercial_requirement,
)

NOW=datetime(2026,10,20,14,tzinfo=timezone.utc)

def test_template_has_every_input_without_secret_leads_or_unearned_approval():
    draft=commercial_intake_template()
    assert set(draft)==INPUT_FIELDS
    assert draft["country"] is None
    assert draft["city"] is None
    assert draft["industry"] is None
    assert draft["requested_qualified_leads"] is None
    assert draft["tenant_ref_sha256"] is None
    assert draft["company_ref_sha256"] is None
    assert draft["currency"] is None
    assert draft["exclusivity"]=="unconfirmed"
    assert draft["zip_codes"]==[]
    assert draft["accepted_event_types"]==[]
    assert draft["budget_minor"] is None
    assert draft["buyer_capacity_verified_units"] is None
    assert draft["company_authorization_owner_receipt"] is None
    assert draft["permission_proof_owner_receipt"] is None
    assert draft["material_specs_owner_receipt"] is None


def test_empty_template_cannot_be_submitted_as_real_customer_order():
    with pytest.raises(ValueError):
        review_commercial_requirement(commercial_intake_template(),as_of=NOW)


def test_print_template_is_plain_json_suitable_for_redirecting_to_owner_file():
    out=subprocess.run(
        [sys.executable,"-B","-m",
         "scripts.print_predictive_commercial_intake_template_20261020",
         "--read-only"],capture_output=True,text=True,check=True,timeout=10,
    )
    assert json.loads(out.stdout)==commercial_intake_template()
    assert not out.stderr


def test_user_entered_nondefault_market_can_be_reviewed_without_fake_contract():
    x=commercial_intake_template()
    x.update(country="GB",state="LON",city="London",industry="agency",
             currency="GBP",requested_qualified_leads=15,
             service_types=["client_acquisition"])
    reviewed=review_commercial_requirement(x,as_of=NOW)
    assert reviewed["city"]=="London"
    assert reviewed["industry"]=="agency"
    assert reviewed["requested_qualified_leads_target_not_inventory"]==15
    assert reviewed["source_customer_order_authenticated"] is False
    assert reviewed["database_writes"] is False
