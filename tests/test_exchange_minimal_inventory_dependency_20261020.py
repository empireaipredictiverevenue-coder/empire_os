"""Standalone Exchange-only source fixture on the production-base branch."""
from copy import deepcopy
from datetime import timedelta
import json

from empire_os.lead_exchange_live_inventory import build_lead_exchange_live_inventory
from tests.exchange_snapshot_fixture_20261020 import fixture, NOW


def test_canonical_inventory_is_not_automatic_fulfilment():
    x=build_lead_exchange_live_inventory(fixture(),now=NOW)
    assert x["state"]=="FRESH_CANONICAL_SNAPSHOT"
    assert x["selected_inventory_records"]==4
    assert x["buyer_seat_records"]==1
    assert x["allocation_candidate_records"]==1
    assert x["delivery_ready_now"]==0
    assert x["payment_authorized"] is False
    assert x["automated_allocation_authorized"] is False
    assert "synthetic-buyer" not in json.dumps(x)
    assert "prospect-synthetic" not in json.dumps(x)


def test_missing_matching_capacity_not_promoted():
    v=fixture()
    v["buyer_seats"][0]["seat_state"]="blocked_missing_evidence"
    v["seat_state_counts"]={"blocked_missing_evidence":1}
    x=build_lead_exchange_live_inventory(v,now=NOW)
    assert x["active_capacity_seat_records"]==0
    assert x["delivery_ready_now"]==0


def test_stale_and_duplicate_sources_not_promoted():
    v=fixture()
    v["observed_at"]=(NOW-timedelta(days=2)).isoformat()
    assert build_lead_exchange_live_inventory(v,now=NOW)["state"]=="STALE_CANONICAL_SNAPSHOT"
    bad=fixture()
    bad["inventory"][0]["prospect_id"]=bad["inventory"][1]["prospect_id"]
    assert build_lead_exchange_live_inventory(bad,now=NOW)["state"]=="HOLD"
