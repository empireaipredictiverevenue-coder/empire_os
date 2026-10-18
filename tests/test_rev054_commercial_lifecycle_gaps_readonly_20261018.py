"""Read-only founder tenant funnel; sensitive row content never emitted."""
import json

from scripts import review_rev054_commercial_lifecycle_gaps_readonly_20261018 as rev

CATS = (
    "correct_db","login_exists","login_no_admin_noinherit",
    "credential_is_scram","capability_is_nologin","exact_set_only_grant",
    "no_other_granted_memberships","tenant_binding_exactly_one",
    "tenant_binding_no_extra_rows","function_exists",
    "capability_function_execute","login_no_commercial_select",
    "login_no_orders_select","login_no_buyers_select",
    "hba_specific_scram_rule_configured","hba_no_parse_errors",
)

def _admin(sql,values,*,bad_catalog=None):
    if sql==rev.CATALOG_SQL:
        return json.dumps({key:key!=bad_catalog for key in CATS})
    if sql==rev.STAGE_SQL:
        return json.dumps(values)
    raise AssertionError("unexpected SQL")


def sample(stage_count=0, buyers=1,orders=1,events=1):
    s={"founder_buyers_sampled":buyers,"founder_orders_sampled":orders}
    s.update({k:(events if k=="tenant_events_sampled" else stage_count) for k in rev.STAGES})
    return s


def test_readonly_source_queries_expose_only_aggregates():
    sql=rev.STAGE_SQL
    assert sql.startswith("BEGIN READ ONLY;")
    assert sql.rstrip().endswith("ROLLBACK;")
    assert "SET LOCAL statement_timeout='7000ms'" in sql
    assert sql.count("LIMIT "+str(rev.LIMIT))==3
    assert sql.count("pg_catalog.jsonb_build_object(")==1
    assert "SELECT pg_catalog.jsonb_build_object(" in sql
    assert sql.count("'"+rev.TENANT+"'::uuid")==2
    assert "SELECT e.id,e.event_type" in sql # internal only, no row export
    assert "SELECT e.id::text" not in sql
    assert "real_payment" not in sql
    assert "INSERT INTO" not in sql
    assert "UPDATE public" not in sql
    assert "DELETE FROM" not in sql


def test_empty_tenant_events_are_not_claimed_zero_revenue():
    result=rev.evaluate_counts(sample(0,0,0,0))
    assert result["status"]=="REV054_BOUNDED_LIFECYCLE_GAP_REVIEW_COMPLETE"
    assert result["first_zero_gate"]=="NO_TENANT_EVENTS_IN_BOUNDED_SCOPE"
    assert result["realised_revenue_verified"] is False
    assert result["complete_daily_revenue_census_verified"] is False
    assert result["customer_records_exported"] is False


def test_cumulative_stage_identifies_recognition_gap():
    x=sample(0,events=2)
    result=rev.evaluate_counts(x)
    assert result["first_zero_gate"]=="FIRST_ZERO_AT_RECOGNIZED"
    assert result["counts"]["tenant_events_sampled"]==2


def test_stage_tracks_deeper_unresolved_payment_gate():
    x=sample(stage_count=1)
    x["settled_order"]=0
    x["lineage_match"]=0
    x["eligible_nonfuture"]=0
    result=rev.evaluate_counts(x)
    assert result["first_zero_gate"]=="FIRST_ZERO_AT_SETTLED_ORDER"
    assert result["payer_or_settlement_externally_verified"] is False


def test_bounded_truncation_is_never_complete_census():
    x=sample(0,buyers=rev.LIMIT,events=rev.LIMIT)
    result=rev.evaluate_counts(x)
    assert result["status"]=="REV054_SAMPLE_TRUNCATED_REQUIRES_WIDER_REVIEW"
    assert result["sample_truncated_or_limit_reached"] is True
    assert result["complete_daily_revenue_census_verified"] is False


def test_rejects_invalid_or_nonmonotone_counts():
    for wrong in (
        dict(sample(0),recognized=3),
        dict(sample(0),flagged_actual=1),
        dict(sample(0),recognized=-1),
        dict(sample(0),recognized=rev.LIMIT+1),
        dict(sample(0),recognized="1"),
        dict(sample(0),recognized=True),
        dict(sample(0),not_an_expected_field=1),
    ):
        try:
            rev.evaluate_counts(wrong)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid aggregate accepted")


def test_no_authority_prevents_full_source_scan():
    def deny_if_source(sql):
        if sql==rev.CATALOG_SQL:
            return json.dumps({key:key!="tenant_binding_exactly_one" for key in CATS})
        raise AssertionError("source inspection must not be called")
    result=rev.review(admin_query=deny_if_source)
    assert result["stage"]=="REV052_AUTHORITY_CATALOG_HOLD"
    assert result["read_only"] is True


def test_readonly_realized_report_is_just_diagnostic():
    values=sample(1)
    result=rev.review(admin_query=lambda sql:_admin(sql,values))
    assert result["status"]=="REV054_BOUNDED_LIFECYCLE_GAP_REVIEW_COMPLETE"
    assert result["first_zero_gate"]=="ALL_RECOGNITION_GATES_HAVE_A_SAMPLE_MATCH"
    assert result["database_mutation"] is False
    assert result["payment_changed"] is False
    assert result["realised_revenue_verified"] is False


def test_sql_error_is_redacted_no_customer_details():
    def denied(sql):
        if sql==rev.CATALOG_SQL:
            return json.dumps({k:True for k in CATS})
        raise RuntimeError("private customer detail must never be output")
    report=rev.review(admin_query=denied)
    assert report["stage"]=="LIFECYCLE_AGGREGATE_QUERY_UNAVAILABLE"
    assert "customer detail" not in json.dumps(report)


def test_root_and_exact_flag_required(monkeypatch,capsys):
    assert rev.main([])==2
    assert "HOLD_EXPLICIT" in capsys.readouterr().out
    monkeypatch.setattr(rev.os,"geteuid",lambda:1000)
    assert rev.main(["--read-only-lifecycle-gaps"])==2
    assert "HOLD_ROOT_LOCAL_REQUIRED" in capsys.readouterr().out
