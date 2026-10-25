"""V4.21: many issued statements / signed evidence, one 30/60/90 cohort."""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import runpy
import pytest

from empire_os.predictive_revenue_v421_statement_chain import (
    SCHEMA,review_v421_statement_chain_held,
)
from empire_os.predictive_revenue_v421_statement_closure import _sequence_hash

ROOT=Path(__file__).resolve().parents[1]
OLD=runpy.run_path(str(
    ROOT/"tests/test_predictive_revenue_v421_statement_closure_20261025.py"
))
NOW=OLD["NOW"]
TENANT=OLD["TENANT"]
BANK=OLD["BANK"]
BUYER=OLD["BUYER"]
BANK_PRIV=OLD["BANK_PRIV"]
BUYER_PRIV=OLD["BUYER_PRIV"]
SIGNED=OLD["SIGNED"]
TWIN=OLD["TWIN"]
signed=OLD["signed"]
pub=OLD["pub"]
source_data=OLD["data"]

START=NOW-timedelta(days=141)


def statements():
    orders,advices,events,_,_=source_data()
    chunks=[]
    preceding_balance=5000
    following_seq=101
    for i in range(4):
        start=START+timedelta(days=i*31)
        end=start+timedelta(days=31)
        subset=tuple(e for e in events if start<=OLD["NOW"].fromisoformat(
            e["cleared_at"])<end)
        positions=tuple({
            "statement_id":f"40000000-0000-4000-8000-{i+1:012d}",
            "event_id":e["event_id"],
            "sequence_no":following_seq+j,
        } for j,e in enumerate(subset))
        credits=sum(e["amount_minor"] for e in subset if e["direction"]=="CREDIT")
        debits=sum(e["amount_minor"] for e in subset if e["direction"]=="DEBIT")
        manifest={
            "statement_id":f"40000000-0000-4000-8000-{i+1:012d}",
            "issuer_id":BANK,"account_digest":"d"*64,
            "tenant_id":TENANT,"currency_code":"USD",
            "window_start":start.isoformat(),
            "window_end":end.isoformat(),
            "issued_at":(end+timedelta(hours=1)).isoformat(),
            "record_count":len(subset),
            "first_sequence":following_seq,
            "last_sequence":following_seq+len(subset)-1,
            "credit_event_count":sum(e["direction"]=="CREDIT" for e in subset),
            "debit_event_count":sum(e["direction"]=="DEBIT" for e in subset),
            "gross_credit_minor":credits,
            "gross_debit_minor":debits,
            "opening_balance_minor":preceding_balance,
            "closing_balance_minor":preceding_balance+credits-debits,
            "sequenced_events_sha256":_sequence_hash(tuple(
                {"sequence_no":p["sequence_no"],"event":e}
                for p,e in zip(positions,subset)
            )),
        }
        chunks.append({"manifest":signed(manifest,BANK_PRIV),
                       "positions":positions})
        preceding_balance+=credits-debits
        following_seq+=len(subset)
    return orders,advices,events,tuple(chunks)


def resign(entry,**updates):
    manifest={k:v for k,v in entry["manifest"].items() if k!="signature_hex"}
    manifest.update(updates)
    return {"manifest":signed(manifest,BANK_PRIV),
            "positions":entry["positions"]}


def review(*,orders=None,advices=None,events=None,chain=None,**overrides):
    original_o,original_a,original_e,original_chain=statements()
    verifier,token=SIGNED()
    kwargs=dict(
        research_twin=TWIN(),signed_crm_bearer=token,
        crm_verifier=verifier,
        original_order_snapshots=original_o if orders is None else orders,
        buyer_remittance_advices=original_a if advices is None else advices,
        external_bank_events=original_e if events is None else events,
        supplied_statements=original_chain if chain is None else chain,
        pinned_buyer_keys={BUYER:pub(BUYER_PRIV)},
        pinned_bank_keys={BANK:pub(BANK_PRIV)},
        as_of=NOW,
    )
    kwargs.update(overrides)
    return review_v421_statement_chain_held(**kwargs)


def test_v421_four_declared_statements_cover_all_mature_horizons_but_never_cash_truth():
    result=review()
    assert result["schema_version"]==SCHEMA
    assert result["status"]=="V421_DECLARED_STATEMENT_CHAIN_CLOSED_HELD"
    assert result["statement_count"]==4
    assert result["internally_closed_statement_count"]==4
    assert result["global_supplied_event_count"]==5
    assert result["events_unassigned_to_statements"]==0
    assert result["declared_chain_contiguous_and_balanced"] is True
    assert all(x["declared_contiguous_statement_calendar_coverage"]
               for x in result["horizons"])
    assert [x["horizon_days"] for x in result["horizons"]]==[30,60,90]
    assert result["orders_with_discrepancies"]==1
    assert result["orphan_external_credit_events"]==1
    assert result["bank_statement_inventory_complete_verified"] is False
    assert result["actual_realised_net_cash_minor"] is None
    assert result["independent_cash_residuals_for_training"] is None
    assert result["training_samples_eligible"]==0
    assert result["production_model_weights_updated"] is False
    assert result["execution_authority"]=="none"


def test_v421_missing_middle_statement_detects_calendar_gap():
    o,a,e,chain=statements()
    report=review(chain=(chain[0],chain[2],chain[3]))
    assert report["status"]=="V421_DECLARED_STATEMENT_CHAIN_GAPS_HELD"
    assert "STATEMENT_DATE_GAP" in report["issues"]
    assert not report["horizons"][2]["declared_contiguous_statement_calendar_coverage"]


def test_v421_balance_and_global_sequence_break_both_detected():
    o,a,e,chain=statements()
    broken=list(chain)
    old=broken[1]["manifest"]
    broken[1]=resign(broken[1],
                     opening_balance_minor=old["opening_balance_minor"]+10,
                     closing_balance_minor=old["closing_balance_minor"]+10,
                     first_sequence=old["first_sequence"]+1,
                     last_sequence=old["last_sequence"]+1)
    report=review(chain=tuple(broken))
    assert "CROSS_STATEMENT_BALANCE_BREAK" in report["issues"]
    assert "CROSS_STATEMENT_SEQUENCE_BREAK" in report["issues"]
    assert report["bank_statement_inventory_complete_verified"] is False


def test_v421_overlapping_statement_windows_cannot_replay_events():
    _,_,events,chain=statements()
    modified=list(chain)
    earlier=START+timedelta(days=10)
    modified[1]=resign(modified[1],
                       window_start=earlier.isoformat(),
                       window_end=(earlier+timedelta(days=31)).isoformat(),
                       issued_at=(earlier+timedelta(days=31,hours=1)).isoformat())
    report=review(chain=tuple(modified))
    assert "STATEMENT_DATE_OVERLAP" in report["issues"]
    assert "REPLAYED_EXTERNAL_EVENT" in report["issues"]
    assert "SINGLE_STATEMENT_NOT_CLOSED" in report["issues"]


def test_v421_account_digest_changes_are_not_one_statement_chain():
    _,_,_,chain=statements()
    modified=list(chain)
    modified[2]=resign(modified[2],account_digest="e"*64)
    report=review(chain=tuple(modified))
    assert "ACCOUNT_OR_ISSUER_CHANGED" in report["issues"]


def test_v421_extra_unassigned_bank_event_is_not_ignored():
    _,_,events,chain=statements()
    new=dict(events[0])
    new["event_id"]="30000000-0000-4000-8000-000000009999"
    new["cleared_at"]=(NOW-timedelta(days=3)).isoformat()
    new={k:v for k,v in new.items() if k!="signature_hex"}
    extended=events+(signed(new,BANK_PRIV),)
    report=review(events=extended)
    assert report["events_unassigned_to_statements"]==1
    assert "EXTERNAL_EVENTS_WITHOUT_STATEMENT" in report["issues"]


def test_v421_duplicate_statement_ids_are_rejected():
    _,_,_,chain=statements()
    with pytest.raises(ValueError,match="DUPLICATE_STATEMENT_ID"):
        review(chain=(chain[0],chain[0]))


def test_v421_future_or_immature_cohort_must_not_generate_forecast_actuals():
    orders,_,_,_=statements()
    recent=tuple(dict(o,accepted_at=(NOW-timedelta(days=40)).isoformat())
                 for o in orders)
    report=review(orders=recent)
    assert report["horizons"][0]["all_selected_orders_mature"] is True
    assert report["horizons"][1]["all_selected_orders_mature"] is False
    assert report["horizons"][2]["all_selected_orders_mature"] is False
    assert report["actual_realised_net_cash_minor"] is None


def test_v421_tampered_statement_signature_is_not_consistent_evidence():
    _,_,_,chain=statements()
    tampered=list(chain)
    tampered[1]={"manifest":dict(chain[1]["manifest"],opening_balance_minor=0),
                 "positions":chain[1]["positions"]}
    with pytest.raises(ValueError,match="INVALID_DOCUMENT_SIGNATURE"):
        review(chain=tuple(tampered))


def test_v421_other_tenant_statement_cannot_join_original_crm():
    _,_,_,chain=statements()
    tampered=list(chain)
    tampered[0]=resign(chain[0],tenant_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
    with pytest.raises(ValueError,match="STATEMENT_TENANT_CURRENCY"):
        review(chain=tuple(tampered))


def test_v421_changing_signed_issuer_without_pinned_identity_is_rejected():
    _,_,_,chain=statements()
    tampered=list(chain)
    tampered[1]=resign(chain[1],issuer_id="unrecognized_bank")
    with pytest.raises(ValueError,match="STATEMENT_ISSUER_KEY_UNKNOWN"):
        review(chain=tuple(tampered))


def test_v421_statement_count_bound_prevents_unbounded_remote_content():
    _,_,_,chain=statements()
    with pytest.raises(ValueError,match="BOUNDED_STATEMENT_CHAIN"):
        review(chain=chain*5)


def test_v421_duplicate_global_bank_event_identity_is_denied():
    _,_,events,_=statements()
    with pytest.raises(ValueError,match="DUPLICATE_EXTERNAL_BANK_EVENT"):
        review(events=events+(events[0],))


def test_v421_no_recent_closing_statement_must_not_prove_full_horizon():
    _,_,_,chain=statements()
    old=review(chain=chain[:2])
    assert old["declared_chain_contiguous_and_balanced"] is True
    assert old["horizons"][0]["declared_contiguous_statement_calendar_coverage"] is True
    assert old["horizons"][1]["declared_contiguous_statement_calendar_coverage"] is True
    assert old["horizons"][2]["declared_contiguous_statement_calendar_coverage"] is False
    assert old["actual_realised_net_cash_minor"] is None


def test_v421_statement_is_not_accepted_as_universal_financial_evidence():
    report=review()
    assert report["all_supplied_order_claims_reconciled"] is False
    assert report["issuer_public_key_independently_attested"] is False
    assert report["original_empiredb_order_population_complete_verified"] is False
    assert report["refund_and_chargeback_finality_verified"] is False
    assert report["verified_30_60_90_cash_forecasts"] is None
    assert all(x["training_ground_truth_eligible"] is False
               for x in report["horizons"])
    assert report["economic_memory_written"] is False
    assert report["funds_moved"] is False
