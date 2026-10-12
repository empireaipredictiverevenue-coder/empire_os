"""Exact aggregate-only source-ledger diagnosis; no live database writes."""
import json
from types import SimpleNamespace

from scripts import probe_canonical_sales_intake_aggregate_readonly as probe


def payload(**overrides):
    d={
        "commercial_acquisition_rows":2,
        "predictive_acquisition_rows":1,
        "sales_acquisition_rows":3,
        "distinct_sales_prospects":2,
        "source_evidence_consistent_rows":2,
        "entity_unlinked_acquisition_rows":2,
        "founder_binding_exact_one_rows":1,
        "founder_binding_missing_or_ambiguous_rows":2,
    }
    d.update(overrides)
    return json.dumps(d)


def test_exact_source_query_is_read_only_and_has_tenant_scope():
    q=probe.SQL
    assert q.count("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;")==1
    assert q.count("ROLLBACK;")==1
    assert "SET LOCAL statement_timeout" in q
    assert "tenant_id=:'founder_tenant'::uuid" in q
    assert "public.prospect_acquisitions" in q
    assert "public.prospect_entity_links" in q
    assert "public.tenant_business_entity_bindings" in q
    assert "binding.binding_kind IN ('owned','managed','customer','prospect')" in q
    assert "evidence #>> '{contact_consent_evidence,consent_to_contact}'" in q
    assert "SELECT jsonb_build_object" in q
    for token in ("INSERT INTO","UPDATE public","DELETE FROM","GRANT ","ALTER TABLE",
                  "TRUNCATE ","CREATE TABLE","SET ROLE"):
        assert token not in q


def test_normal_aggregate_is_not_claimed_as_visibility_or_revenue():
    seen=[]
    def process(argv,**kwargs):
        seen.append((argv,kwargs))
        return SimpleNamespace(returncode=0,stdout=payload(),stderr="")
    result=probe.run(euid=0,command_runner=process)
    assert result["status"]=="SALES_ACQUISITION_SOURCE_OBSERVED_REVIEW_REQUIRED"
    assert result["sales_acquisition_rows"]==3
    assert result["founder_binding_exact_one_rows"]==1
    assert result["founder_crm_delivery_verified"] is False
    assert result["outbound_sent"] is False
    assert result["database_writes"] is False
    argv,kwargs=seen[0]
    assert argv[:4]==["/usr/sbin/runuser","-u","postgres","--"]
    assert kwargs["input"]==probe.SQL
    assert kwargs["timeout"]==16
    assert kwargs["env"]["PGCONNECT_TIMEOUT"]=="4"
    assert "check" in kwargs and kwargs["check"] is False
    assert "founder_tenant" not in json.dumps(result)


def test_unprivileged_exec_never_touches_db():
    result=probe.run(euid=1000,command_runner=lambda *a,**kw:
                     (_ for _ in ()).throw(AssertionError("no DB")))
    assert result["status"]=="BLOCKED"
    assert result["reason_code"]=="PRIVILEGED_LOCAL_OPERATOR_REQUIRED"


def test_zero_source_is_not_claim_of_complete_crm_e2e():
    result=probe.classify(privileged=True,returncode=0,
                          stdout=payload(commercial_acquisition_rows=0,
                          predictive_acquisition_rows=0,
                          sales_acquisition_rows=0,distinct_sales_prospects=0,
                          source_evidence_consistent_rows=0,
                          entity_unlinked_acquisition_rows=0,
                          founder_binding_exact_one_rows=0,
                          founder_binding_missing_or_ambiguous_rows=0))
    assert result["status"]=="NO_SALES_ACQUISITION_IN_CANONICAL_SOURCE"
    assert result["founder_crm_delivery_verified"] is False


def test_reject_any_driver_error_and_uncertain_count_with_no_leaks():
    for value in (
        "secret-database-uri", "",
        "{}", "[1,2,3]",
        payload(sales_acquisition_rows=2),
        payload(founder_binding_exact_one_rows=-1),
        payload(source_evidence_consistent_rows=999),
        payload(founder_binding_missing_or_ambiguous_rows=0),
        payload(commercial_acquisition_rows=True),
        payload()+"\\n"+payload(),
    ):
        result=probe.classify(privileged=True,returncode=0,stdout=value)
        assert result["status"]=="UNVERIFIED"
        assert "secret-database-uri" not in str(result)
    assert probe.classify(privileged=True,returncode=2,stdout=payload())[
        "reason_code"
    ]=="CANONICAL_QUERY_FAILED"


def test_runner_exception_does_not_expose_error():
    def failed(*args,**kwargs):
        raise OSError("postgres password token sample")
    report=probe.run(euid=0,command_runner=failed)
    assert report["status"]=="UNVERIFIED"
    assert "password" not in json.dumps(report)
