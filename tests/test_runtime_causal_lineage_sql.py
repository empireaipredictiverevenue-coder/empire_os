"""Compile/exercise extracted canonical functions in disposable socket-free PG.

Does not apply/run a migration file or connect to a production database.
"""
import copy
import json
from pathlib import Path
import re

import pytest

from test_empiredb_materializer_bootstrap import execute
from test_empiredb_actual_cost_realized_margin_hardening import SCHEMA
from test_runtime_causal_lineage_continuity import completed, lineage, TENANT, OPPORTUNITY, ORDER

SQL = Path('migrations/empiredb/036_runtime_causal_lineage_continuity.sql')
CASE = '50000000-0000-4000-8000-000000000001'
BUYER = '60000000-0000-4000-8000-000000000001'
REPLY = '70000000-0000-4000-8000-000000000001'
INTENT = '80000000-0000-4000-8000-000000000001'
REQUEST = '90000000-0000-4000-8000-000000000001'
PROOF = 'a0000000-0000-4000-8000-000000000001'


def literal(value):
    return "'"+json.dumps(value).replace("'","''")+"'::jsonb"


def extracted_functions():
    return re.findall(r'CREATE OR REPLACE FUNCTION public\.[\s\S]*?\n\$\$;',SQL.read_text())


@pytest.fixture
def database(execute):
    execute('postgres','CREATE DATABASE empiredb;')
    execute('empiredb',SCHEMA)
    execute('empiredb', '''
CREATE ROLE empire_closer_planner NOLOGIN NOINHERIT;
CREATE ROLE empire_outcome_recorder NOLOGIN NOINHERIT;
CREATE ROLE empire_outcome_reader NOLOGIN NOINHERIT;
GRANT USAGE ON SCHEMA public TO empire_closer_planner,empire_outcome_recorder,empire_outcome_reader;
SET ROLE empiredb_migrator;
ALTER TABLE public.fulfilment_orders ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE public.fulfilment_orders ADD quantity integer DEFAULT 1,
 ADD expected_margin_cents bigint DEFAULT 0, ADD delivery_payload jsonb DEFAULT '{}',
 ADD delivered_at timestamptz, ADD confirmed_at timestamptz, ADD outcome_at timestamptz;
ALTER TABLE public.commercial_outcomes ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE public.commercial_outcomes ADD delivery_outcome text, ADD conversion_outcome text,
 ADD buyer_satisfaction numeric, ADD evidence_kind text, ADD evidence_reference text,
 ADD evidence jsonb DEFAULT '{}', ADD idempotency_key text UNIQUE, ADD actor text,
 ADD recorded_at timestamptz DEFAULT clock_timestamp();
CREATE TABLE public.buyers(id uuid PRIMARY KEY,org_id uuid);
CREATE TABLE public.closer_cases(id uuid PRIMARY KEY,reply_id uuid,outbound_intent_id uuid,
 buyer_id uuid,prospect_id uuid,entity_id uuid,opportunity_id uuid,fulfilment_order_id uuid,
 state text,updated_at timestamptz);
CREATE TABLE public.outbound_replies(id uuid PRIMARY KEY,intent_id uuid,classification text,
 confidence numeric,received_at timestamptz,subject text,body_text text,from_contact text);
CREATE TABLE public.outbound_intents(id uuid PRIMARY KEY,subject text,offer_key text,metadata jsonb);
CREATE TABLE public.buyer_candidate_reviews(id uuid PRIMARY KEY,contact_name text);
CREATE TABLE public.buyer_capacity_intakes(id uuid DEFAULT gen_random_uuid(),closer_case_id uuid UNIQUE,
 buyer_id uuid,source_reply_ids uuid[],territory text,daily_cap integer,delivery_route text,
 delivery_reference text,evidence jsonb,state text,updated_at timestamptz);
CREATE TABLE public.closer_events(case_id uuid,event_type text,actor text,payload jsonb);
GRANT SELECT,INSERT,UPDATE ON public.closer_cases,public.buyer_capacity_intakes,
 public.fulfilment_orders,public.closer_events TO empire_closer_planner;
GRANT SELECT ON public.outbound_replies,public.outbound_intents,public.buyers,
 public.buyer_candidate_reviews TO empire_closer_planner;
GRANT SELECT,INSERT ON public.commercial_outcomes TO empire_outcome_recorder;
GRANT SELECT,UPDATE ON public.fulfilment_orders TO empire_outcome_recorder;
GRANT INSERT ON public.commercial_events TO empire_outcome_recorder;
GRANT SELECT ON public.fulfilment_orders,public.commercial_outcomes,public.commercial_events TO empire_outcome_reader;
RESET ROLE;
''')
    # Function bodies only: no migration BEGIN/guard/activation statements.
    actual=Path('migrations/empiredb/029_actual_cost_realized_margin_hardening.sql').read_text()
    start=actual.index('CREATE OR REPLACE FUNCTION public.get_verified_actual_cost_evidence(')
    end=actual.index('\n$actual_cost$;',start)+len('\n$actual_cost$;')
    execute('empiredb','SET ROLE empiredb_migrator;\n'+actual[start:end]+'\n'+'\n'.join(extracted_functions())+'''
REVOKE ALL ON FUNCTION public.validate_commercial_causal_lineage(jsonb),
 public.merge_commercial_causal_lineage(jsonb,jsonb),public.guard_order_causal_lineage(),
 public.get_verified_actual_cost_evidence(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.validate_commercial_causal_lineage(jsonb),
 public.merge_commercial_causal_lineage(jsonb,jsonb) TO empire_closer_planner,empire_outcome_recorder,empire_revenue_recognizer;
GRANT EXECUTE ON FUNCTION public.get_verified_actual_cost_evidence(uuid) TO empire_revenue_recognizer;
CREATE TRIGGER guard_order_causal_lineage BEFORE UPDATE ON public.fulfilment_orders
 FOR EACH ROW EXECUTE FUNCTION public.guard_order_causal_lineage();
RESET ROLE;
''')
    return execute


def capacity_setup(database, work):
    causal=lineage(work)
    database('empiredb',f'''
SET ROLE empiredb_migrator;
INSERT INTO public.buyers VALUES ('{BUYER}','{TENANT}');
INSERT INTO public.outbound_intents(id,metadata) VALUES ('{INTENT}',
 {literal(dict(opportunity_key=causal['opportunity_key'],department_work_id=work['id']))});
INSERT INTO public.outbound_replies(id,intent_id,classification) VALUES ('{REPLY}','{INTENT}','positive');
INSERT INTO public.closer_cases(id,reply_id,outbound_intent_id,buyer_id,prospect_id,opportunity_id,state)
 VALUES ('{CASE}','{REPLY}','{INTENT}','{BUYER}','{REPLY}','{OPPORTUNITY}','engaged');
RESET ROLE;
SET ROLE empire_closer_planner;
SELECT public.record_buyer_capacity_intake('{CASE}','{REPLY}','Austin',10,'email',NULL,
 {literal(dict(causal_lineage=causal,independent='capacity'))},'test');
SELECT public.prepare_fulfilment_order_from_capacity('{CASE}','test');
RESET ROLE;
''')
    return causal


def order_setup(database, causal):
    database('empiredb',f'''
SET ROLE empiredb_migrator;
INSERT INTO public.fulfilment_orders(id,buyer_id,entity_id,opportunity_id,state,price_cents,delivered_at,commercial_payload)
 VALUES ('{ORDER}','{BUYER}','c0000000-0000-4000-8000-000000000001','{OPPORTUNITY}','delivered',10000,clock_timestamp(),
 {literal(dict(existing='preserved',commercial_terms_sha256='b'*64,causal_lineage=causal))});
RESET ROLE;
''')


def record_sql(evidence, key='test:outcome:001'):
    return f"""SET ROLE empire_outcome_recorder;
SELECT public.record_commercial_outcome('{ORDER}','confirmed','won',4,'buyer_feedback',
 'independent:reply',{literal(evidence)},'{key}','test');
RESET ROLE;"""


def test_canonical_capacity_order_preserves_lineage_and_payload(database,completed):
    causal=capacity_setup(database,completed)
    database('empiredb',f'''
DO $$ DECLARE o public.fulfilment_orders%ROWTYPE; BEGIN
 SELECT * INTO o FROM public.fulfilment_orders;
 IF o.commercial_payload->'causal_lineage' IS DISTINCT FROM {literal(causal)}
    OR o.commercial_payload->>'binding_commercial_terms'<>'false'
    OR o.opportunity_id IS DISTINCT FROM '{OPPORTUNITY}'::uuid THEN
   RAISE EXCEPTION 'order lineage lost'; END IF;
END $$;
SET ROLE empire_closer_planner;
SELECT public.prepare_fulfilment_order_from_capacity('{CASE}','test');
RESET ROLE;
''')
    database('empiredb',"UPDATE public.fulfilment_orders SET commercial_payload=commercial_payload-'causal_lineage';",
             expected_error='persisted order causal lineage is immutable')


def test_canonical_outcome_and_event_read_preserve_real_identity(database,completed):
    causal=lineage(completed);order_setup(database,causal)
    database('empiredb',record_sql({'independent':'preserved'}))
    database('empiredb',record_sql({'independent':'preserved'}))
    database('empiredb',f'''
DO $$ DECLARE x public.commercial_outcomes%ROWTYPE; e public.commercial_events%ROWTYPE; p jsonb; BEGIN
 SELECT * INTO x FROM public.commercial_outcomes;
 SELECT * INTO e FROM public.commercial_events WHERE event_type='outcome_recorded';
 IF x.evidence->'causal_lineage' IS DISTINCT FROM {literal(causal)}
    OR x.evidence->>'independent'<>'preserved'
    OR e.payload->'causal_lineage' IS DISTINCT FROM x.evidence->'causal_lineage'
    OR e.payload->>'outcome_ref'<>'canonical:commercial_outcomes:'||x.id::text
    OR (e.payload->>'actual_revenue')::boolean IS NOT FALSE THEN
   RAISE EXCEPTION 'outcome event continuity lost'; END IF;
 SET LOCAL ROLE empire_outcome_reader;
 p:=public.get_commercial_outcome_feedback(10)->0;
 IF p->>'id'<>x.id::text OR p->'evidence' IS DISTINCT FROM x.evidence
    OR p->>'tenant_id'<>'{TENANT}' OR (p->>'actual_revenue')::boolean IS NOT FALSE THEN
   RAISE EXCEPTION 'read projection lost identity'; END IF;
END $$;
''')


def test_contradictory_outcome_and_replay_fail_closed(database,completed):
    causal=lineage(completed);order_setup(database,causal)
    for key in ('tenant_id','opportunity_key','opportunity_id','prediction_ref','decision_ref','execution_ref'):
        changed={**causal,key:'wrong'}
        database('empiredb',record_sql({'causal_lineage':changed}),expected_error='contradictory commercial causal lineage')
        database('empiredb',record_sql({key:'wrong'}),expected_error='contradictory causal field')
    database('empiredb',record_sql({'independent':'preserved'}))
    database('empiredb',record_sql({'independent':'changed'}),expected_error='idempotency key belongs to different outcome')


def test_revenue_remains_independent_and_preserves_causal_refs(database,completed):
    causal=lineage(completed);order_setup(database,causal)
    database('empiredb',f"SET ROLE empire_revenue_recognizer; SELECT public.recognize_bsc_revenue('{ORDER}','test');",
             expected_error='no revenue-eligible verified BSC settlement evidence')
    database('empiredb',f'''
RESET ROLE; SET ROLE empiredb_migrator;
INSERT INTO public.bsc_payment_requests VALUES ('{REQUEST}','{ORDER}','direct','approved',clock_timestamp(),'human','{'b'*64}',100);
INSERT INTO public.bsc_payment_evidence VALUES ('{PROOF}','{REQUEST}','0xtest',clock_timestamp());
RESET ROLE;
''')
    database('empiredb',f"SET ROLE empire_revenue_recognizer; SELECT public.recognize_bsc_revenue('{ORDER}','test');",
             expected_error='verified order-bound actual acquisition and fulfilment cost evidence required')
    database('empiredb',f'''
SET ROLE empiredb_migrator;
INSERT INTO public.commercial_evidence_registry VALUES
 ('b0000000-0000-4000-8000-000000000001','acquisition_cost','{ORDER}',1000,'per_order','provider_invoice','invoice:1','verified',clock_timestamp()),
 ('b0000000-0000-4000-8000-000000000002','fulfilment_cost','{ORDER}',2000,'flat','internal_actual','actual:1','verified',clock_timestamp());
RESET ROLE;SET ROLE empire_revenue_recognizer;
SELECT public.recognize_bsc_revenue('{ORDER}','test');
RESET ROLE;
DO $$ DECLARE e public.commercial_events%ROWTYPE; BEGIN
 SELECT * INTO e FROM public.commercial_events WHERE event_type='revenue_recognized';
 IF e.payload->'causal_lineage' IS DISTINCT FROM {literal(causal)}
    OR e.amount_cents<>10000 OR e.cost_cents<>3000 OR e.margin_cents<>7000
    OR (e.payload->>'actual_cost_evidence_verified')::boolean IS NOT TRUE THEN
   RAISE EXCEPTION 'revenue lineage/truth lost'; END IF;
END $$;
SET ROLE empire_revenue_recognizer;
SELECT public.recognize_bsc_revenue('{ORDER}','test');
RESET ROLE;
''')


def test_sql_contract_adds_no_table_or_authority():
    sql=SQL.read_text()
    assert 'CREATE TABLE' not in sql and 'CREATE ROLE' not in sql and 'SECURITY DEFINER' not in sql
    assert 'HELD' in sql and 'FROM PUBLIC, empiredb_app' in sql
    assert 'UPDATE public.commercial_outcomes' not in sql
    assert 'CREATE OR REPLACE FUNCTION public.recognize_bsc_revenue' in sql


def test_sql_output_enters_existing_v2b_feedback_and_memory(database,completed,tmp_path):
    """Use rows actually produced by extracted SQL, not reconstructed projections."""
    from datetime import datetime,timezone
    from empire_os.execution_bus_data_repository import ExecutionBusDataRepository
    from empire_os.economic_memory import build_economic_memory_snapshot
    from empire_os.predictive_calibration import review_commercial_prediction
    from test_runtime_causal_lineage_continuity import Gateway
    causal=lineage(completed);order_setup(database,causal)
    database('empiredb',record_sql({'independent':'real-fixture-outcome'}))
    database('empiredb',f'''
SET ROLE empiredb_migrator;
INSERT INTO public.buyers VALUES ('{BUYER}','{TENANT}');
INSERT INTO public.bsc_payment_requests VALUES ('{REQUEST}','{ORDER}','direct','approved',clock_timestamp(),'human','{'b'*64}',100);
INSERT INTO public.bsc_payment_evidence VALUES ('{PROOF}','{REQUEST}','0xtest',clock_timestamp());
INSERT INTO public.commercial_evidence_registry VALUES
 ('b0000000-0000-4000-8000-000000000001','acquisition_cost','{ORDER}',1000,'per_order','provider_invoice','invoice:1','verified',clock_timestamp()),
 ('b0000000-0000-4000-8000-000000000002','fulfilment_cost','{ORDER}',2000,'flat','internal_actual','actual:1','verified',clock_timestamp());
RESET ROLE; SET ROLE empire_revenue_recognizer;
SELECT public.recognize_bsc_revenue('{ORDER}','test');
RESET ROLE;
''')
    output=database('empiredb',"""
COPY (SELECT jsonb_build_object(
 'fulfilment_orders',(SELECT jsonb_agg(to_jsonb(o)) FROM public.fulfilment_orders o),
 'buyers',(SELECT jsonb_agg(to_jsonb(b)) FROM public.buyers b),
 'commercial_outcomes',(SELECT jsonb_agg(to_jsonb(c)) FROM public.commercial_outcomes c),
 'commercial_events',(SELECT jsonb_agg(to_jsonb(e)) FROM public.commercial_events e WHERE event_type='revenue_recognized'),
 'bsc_payment_requests',(SELECT jsonb_agg(to_jsonb(r)) FROM public.bsc_payment_requests r),
 'bsc_payment_evidence',(SELECT jsonb_agg(to_jsonb(p)) FROM public.bsc_payment_evidence p)
)) TO STDOUT;
""")
    start=output.find('{"buyers":')
    assert start>=0, output
    rows=json.JSONDecoder().raw_decode(output[start:])[0]
    repo=ExecutionBusDataRepository(Gateway(rows))
    as_of=datetime(2027,1,1,tzinfo=timezone.utc)
    f=repo.verified_outcome_feedback(ORDER,tenant_id=TENANT,repo_root=tmp_path,as_of=as_of)
    p=dict(tenant_id=TENANT,opportunity_key=causal['opportunity_key'],prediction_ref=causal['prediction_ref'],
        prediction_type='conversion_probability',predicted_probability=0.6,predicted_at='2026-10-01T12:00:00+00:00',
        horizon_until='2027-01-01T00:00:00+00:00',evidence_refs=[causal['prediction_ref']])
    review=review_commercial_prediction(prediction=p,feedback=f,tenant_id=TENANT,as_of=as_of)
    m=build_economic_memory_snapshot(executive_evaluation={},department_work=[completed],
        cortex_learning={'packets':[f['cortex_packet']]},verified_feedback=[f],calibration_reviews=[review],
        tenant_id=TENANT,as_of=as_of)
    assert m['decision_outcome_attribution_count']==1
    assert f['actual_revenue_cents']==10000 and f['actual_cost_cents']==3000
    assert f['outcome_ref']=='canonical:commercial_outcomes:'+rows['commercial_outcomes'][0]['id']
    assert m['decision_outcome_attributions'][0]['execution_ref']==causal['execution_ref']
    from empire_os.economic_memory import refresh_economic_memory_snapshot
    from empire_os.astra_feedback import build_verified_learning_feedback
    runtime=refresh_economic_memory_snapshot(tmp_path,repository=repo,fulfilment_order_ids=[ORDER],
        tenant_id=TENANT,original_predictions={p['prediction_ref']:p},as_of=as_of)
    assert runtime['decision_outcome_attribution_count']==1
    assert runtime['calibration_evidence'][0]['prediction_ref']==p['prediction_ref']
    assert build_verified_learning_feedback(runtime,tenant_id=TENANT,as_of=as_of)['execution_authority']=='none'
    assert (tmp_path/'runtime/economic_memory/latest.json').exists()
