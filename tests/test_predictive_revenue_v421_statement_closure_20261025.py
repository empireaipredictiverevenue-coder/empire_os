"""V4.21 offline signed-statement bounds, event census and balance closure."""
from __future__ import annotations
from datetime import timedelta
from pathlib import Path
import runpy
import pytest

from empire_os.predictive_revenue_v421_statement_closure import (
    SCHEMA,review_v421_supplied_bank_statement_held,_sequence_hash,
)

ROOT=Path(__file__).resolve().parents[1]
PREVIOUS=runpy.run_path(
    str(ROOT/"tests/test_predictive_revenue_v421_dual_entry_20261025.py")
)
TWIN=PREVIOUS["TWIN"]
SIGNED=PREVIOUS["SIGNED"]
BUYER=PREVIOUS["BUYER"]
BANK=PREVIOUS["BANK"]
BUYER_PRIV=PREVIOUS["BUYER_PRIV"]
BANK_PRIV=PREVIOUS["BANK_PRIV"]
TENANT=PREVIOUS["TENANT"]
NOW=PREVIOUS["NOW"]
pub=PREVIOUS["pub"]
signed=PREVIOUS["signed"]
fixtures=PREVIOUS["fixtures"]

STATEMENT_ID="40000000-0000-4000-8000-000000000001"
WINDOW_START=(NOW-timedelta(days=137)).isoformat()
WINDOW_END=(NOW-timedelta(days=125)).isoformat()
ISSUED=(NOW-timedelta(days=124)).isoformat()


def data():
    orders,advices,events=fixtures()
    events=tuple(
        signed({**{k:v for k,v in event.items() if k!="signature_hex"},
                "cleared_at":(NOW-timedelta(days=135-i)).isoformat()},
               BANK_PRIV)
        for i,event in enumerate(events)
    )
    positions=tuple(
        {"statement_id":STATEMENT_ID,
         "event_id":event["event_id"],"sequence_no":101+i}
        for i,event in enumerate(events)
    )
    credit=sum(e["amount_minor"] for e in events if e["direction"]=="CREDIT")
    debit=sum(e["amount_minor"] for e in events if e["direction"]=="DEBIT")
    manifest={
        "statement_id":STATEMENT_ID,
        "issuer_id":BANK,
        "account_digest":"d"*64,
        "tenant_id":TENANT,
        "currency_code":"USD",
        "window_start":WINDOW_START,
        "window_end":WINDOW_END,
        "issued_at":ISSUED,
        "record_count":len(events),
        "first_sequence":101,
        "last_sequence":105,
        "credit_event_count":4,
        "debit_event_count":1,
        "gross_credit_minor":credit,
        "gross_debit_minor":debit,
        "opening_balance_minor":5000,
        "closing_balance_minor":5000+credit-debit,
        "sequenced_events_sha256":_sequence_hash(tuple(
            {"sequence_no":position["sequence_no"],"event":event}
            for position,event in zip(positions,events)
        )),
    }
    return orders,advices,events,positions,signed(manifest,BANK_PRIV)


def review(*,orders=None,advices=None,events=None,positions=None,manifest=None,
           **overrides):
    o,a,b,p,m=data()
    verifier,token=SIGNED()
    params=dict(
        research_twin=TWIN(),signed_crm_bearer=token,crm_verifier=verifier,
        original_order_snapshots=o if orders is None else orders,
        buyer_remittance_advices=a if advices is None else advices,
        external_bank_events=b if events is None else events,
        statement_positions=p if positions is None else positions,
        statement_manifest=m if manifest is None else manifest,
        pinned_buyer_keys={BUYER:pub(BUYER_PRIV)},
        pinned_bank_keys={BANK:pub(BANK_PRIV)},
        as_of=NOW,
    )
    params.update(overrides)
    return review_v421_supplied_bank_statement_held(**params)


def resign(m,**changes):
    new={k:v for k,v in m.items() if k!="signature_hex"}
    new.update(changes)
    return signed(new,BANK_PRIV)


def test_v421_signed_statement_can_be_internally_closed_but_never_verified_cash():
    result=review()
    assert result["schema_version"]==SCHEMA
    assert result["status"]=="V421_SUPPLIED_STATEMENT_INTERNALLY_CLOSED_HELD"
    assert result["internal_supplied_statement_consistent"] is True
    assert result["declared_record_count"]==5
    assert result["supplied_event_count"]==5
    assert result["gross_credit_minor_in_supplied_events"]==22499
    assert result["gross_debit_minor_in_supplied_events"]==2000
    assert result["reconciliation_matched_order_claims"]==1
    assert result["reconciliation_discrepant_orders"]==1
    assert result["reconciliation_orphan_external_credit_events"]==1
    assert result["issuer_public_key_proven_independently"] is False
    assert result["complete_bank_account_window_population_verified"] is False
    assert result["all_bank_statement_windows_provided_verified"] is False
    assert result["accepted_order_cash_baseline_verified_minor"] is None
    assert result["verified_30_60_90_cash_forecasts"] is None
    assert result["training_samples_eligible"]==0
    assert result["model_weights_updated"] is False
    assert result["execution_authority"]=="none"


def test_v421_omitted_bank_event_is_reported_as_missing_evidence():
    o,a,events,positions,manifest=data()
    result=review(events=events[:-1],positions=positions,manifest=manifest)
    assert result["status"]=="V421_SUPPLIED_STATEMENT_GAPS_HELD"
    assert result["internal_supplied_statement_consistent"] is False
    assert "INCOMPLETE_EVENT_SEQUENCE_BINDING" in result["issues"]
    assert "SIGNED_STATEMENT_EVENT_COUNT_MISMATCH" in result["issues"]
    assert "EVENT_CONTENT_DIGEST_MISMATCH" in result["issues"]


def test_v421_extra_event_without_position_fails_closed():
    o,a,events,positions,manifest=data()
    result=review(positions=positions[:-1])
    assert "INCOMPLETE_EVENT_SEQUENCE_BINDING" in result["issues"]
    assert result["sequence_binding_missing_count"]==1


def test_v421_duplicate_and_gap_sequence_detected_without_promoting():
    _,_,events,positions,manifest=data()
    repeat=tuple(dict(x) for x in positions)
    repeat=list(repeat)
    repeat[1]["sequence_no"]=repeat[0]["sequence_no"]
    result=review(positions=tuple(repeat))
    assert "DUPLICATED_SEQUENCE" in result["issues"]
    assert "MISSING_OR_OUT_OF_RANGE_SEQUENCE" in result["issues"]
    assert result["accepted_order_cash_baseline_verified_minor"] is None


@pytest.mark.parametrize("field,value,expected",[
    ("record_count",6,"STATEMENT_ROW_COUNT_MISMATCH"),
    ("credit_event_count",5,"CREDIT_DEBIT_EVENT_COUNTS_MISMATCH"),
    ("gross_credit_minor",22400,"CREDIT_DEBIT_TOTALS_MISMATCH"),
    ("closing_balance_minor",12345,"OPENING_CLOSING_BALANCE_MISMATCH"),
    ("sequenced_events_sha256","f"*64,"EVENT_CONTENT_DIGEST_MISMATCH"),
])
def test_v421_bank_signed_inconsistent_manifest_is_still_rejected(field,value,expected):
    _,_,_,_,manifest=data()
    result=review(manifest=resign(manifest,**{field:value}))
    assert expected in result["issues"]
    assert result["internal_supplied_statement_consistent"] is False


def test_v421_tampered_statement_signature_rejected():
    _,_,_,_,manifest=data()
    forged=dict(manifest,closing_balance_minor=100)
    with pytest.raises(ValueError,match="INVALID_DOCUMENT_SIGNATURE"):
        review(manifest=forged)


def test_v421_tampered_bank_event_signature_rejected():
    _,_,events,_,_=data()
    modified=list(events)
    modified[0]=dict(modified[0],amount_minor=9999)
    with pytest.raises(ValueError,match="INVALID_DOCUMENT_SIGNATURE"):
        review(events=tuple(modified))


def test_v421_bank_manifest_wrong_tenant_and_currency_denied():
    _,_,_,_,manifest=data()
    with pytest.raises(ValueError,match="TENANT_CURRENCY"):
        review(manifest=resign(manifest,tenant_id=PREVIOUS["OTHER"]))
    with pytest.raises(ValueError,match="TENANT_CURRENCY"):
        review(manifest=resign(manifest,currency_code="GBP"))


def test_v421_window_mismatches_and_future_issued_at_fail_closed():
    _,_,events,positions,manifest=data()
    result=review(manifest=resign(
        manifest,window_start=(NOW-timedelta(days=134)).isoformat()
    ))
    assert result["event_outside_window_count"]>0
    assert "EVENT_OUTSIDE_WINDOW" in result["issues"]
    with pytest.raises(ValueError,match="WINDOW_OR_ISSUE_TIME"):
        review(manifest=resign(
            manifest,issued_at=(NOW+timedelta(days=1)).isoformat()
        ))


def test_v421_never_uses_buyer_key_as_bank_key():
    with pytest.raises(ValueError,match="MUST_BE_SEPARATE"):
        review(pinned_bank_keys={BANK:pub(BUYER_PRIV)})


def test_v421_event_issuer_must_match_statement_issuer_even_with_valid_keys():
    _,_,events,positions,manifest=data()
    other_private=PREVIOUS["Ed25519PrivateKey"].from_private_bytes(bytes([3])*32)
    other_issuer="second_bank"
    changed=list(events)
    unsigned={k:v for k,v in changed[0].items() if k!="signature_hex"}
    changed[0]=signed({**unsigned,"issuer_id":other_issuer},other_private)
    report=review(events=tuple(changed),pinned_bank_keys={
        BANK:pub(BANK_PRIV),other_issuer:pub(other_private)
    })
    assert "EVENT_ISSUER_MISMATCH" in report["issues"]


def test_v421_no_production_io_in_statement_reader():
    content=(ROOT/"empire_os/predictive_revenue_v421_statement_closure.py").read_text()
    for forbidden in ("psycopg.connect(", "INSERT INTO ", "execute_payment(",
                      "send_email(", "model.fit(", "systemctl", "redis.Redis("):
        assert forbidden not in content


def test_v421_malformed_large_sequence_range_is_bounded_not_expanded():
    _,_,_,_,manifest=data()
    report=review(manifest=resign(manifest,last_sequence=10000000))
    assert "DECLARED_SEQUENCE_RANGE_MISMATCH" in report["issues"]
    assert "MISSING_OR_OUT_OF_RANGE_SEQUENCE" in report["issues"]
    assert report["training_samples_eligible"]==0


def test_v421_tampered_position_statement_id_rejected():
    _,_,_,positions,_=data()
    altered=list(positions)
    altered[0]=dict(altered[0],statement_id=
                    "40000000-0000-4000-8000-000000000002")
    with pytest.raises(ValueError,match="FOREIGN_STATEMENT_SEQUENCE"):
        review(positions=tuple(altered))


def test_v421_zero_bank_events_never_mean_real_zero_cash():
    _,_,_,_,manifest=data()
    empty=resign(manifest,
                 record_count=0,first_sequence=1,last_sequence=0,
                 credit_event_count=0,debit_event_count=0,
                 gross_credit_minor=0,gross_debit_minor=0,
                 closing_balance_minor=manifest["opening_balance_minor"],
                 sequenced_events_sha256=_sequence_hash(()))
    report=review(events=(),positions=(),manifest=empty)
    assert report["internal_supplied_statement_consistent"] is True
    assert report["reconciliation_matched_order_claims"]==0
    assert report["complete_bank_account_window_population_verified"] is False
    assert report["accepted_order_cash_baseline_verified_minor"] is None


def test_v421_one_12_day_bank_statement_never_covers_30_60_90_windows():
    result=review()
    coverage=result["declared_30_60_90_window_coverage"]
    assert [c["horizon_days"] for c in coverage]==[30,60,90]
    assert not any(c["one_supplied_statement_spans_order_horizon"] for c in coverage)
    assert not any(c["bank_cash_ground_truth_eligible"] for c in coverage)


def test_v421_31_day_declared_window_can_cover_30_days_not_60_or_90():
    _,_,_,_,manifest=data()
    changed=resign(
        manifest,
        window_start=(NOW-timedelta(days=140)).isoformat(),
        window_end=(NOW-timedelta(days=109)).isoformat(),
        issued_at=(NOW-timedelta(days=108)).isoformat(),
    )
    result=review(manifest=changed)
    coverage=result["declared_30_60_90_window_coverage"]
    assert [x["one_supplied_statement_spans_order_horizon"] for x in coverage]==[
        True,False,False
    ]
    assert result["internal_supplied_statement_consistent"] is True
    assert all(not x["bank_cash_ground_truth_eligible"] for x in coverage)
    assert result["accepted_order_cash_baseline_verified_minor"] is None
