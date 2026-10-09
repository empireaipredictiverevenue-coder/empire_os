"""Offline canonical FK bridge; no database, sending or service operations."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from uuid import UUID

import pytest

import scripts.refresh_adaptive_outreach_optimizer as runtime
from empire_os.adaptive_outreach_optimizer import (
    build_performance_snapshot, select_message_arms, _bucket,
    MIN_DELIVERED_PER_ARM, SEGMENT_MIN_DELIVERED, EXPLORATION_FRACTION,
)
from empire_os.canonical_data_gateway import DataGatewayOperationUnsupported
from empire_os.data_backends.empiredb import EmpireDbProvider
from empire_os.data_cloud_contract import DataBackend
from empire_os.data_query import FilterOperator
from empire_os.execution_bus_data_repository import ExecutionBusDataRepository
from empire_os.outcome_feedback import validate_verified_feedback
from empire_os.reply_classifier import classify_reply_text
from test_runtime_causal_lineage_continuity import completed, records, lineage, TENANT, OPPORTUNITY, ORDER, NOW, THEN
from test_data_cloud_empiredb_provider import FakeConnection, FakeConnector, Cursor

INTENT = '50000000-0000-4000-8000-000000000001'
PROSPECT = '60000000-0000-4000-8000-000000000001'
CASE = '70000000-0000-4000-8000-000000000001'
REPLY = '80000000-0000-4000-8000-000000000001'


class Gateway:
    backend = DataBackend.EMPIREDB

    def __init__(self, tables):
        self.tables = tables
        self.queries = []

    def configured(self):
        return True

    def snapshot(self):
        class Snapshot:
            def as_dict(self): return {'primary_backend': 'empiredb'}
        return Snapshot()

    def query(self, table, columns='*', *, filters=(), order=(), limit=1000, offset=0):
        self.queries.append((table, columns, filters))
        rows = deepcopy(self.tables.get(table, []))
        for item in filters:
            if item.operator == FilterOperator.EQ:
                rows = [row for row in rows if str(row.get(item.column)) == str(item.value)]
            elif item.operator == FilterOperator.GTE:
                rows = [row for row in rows if datetime.fromisoformat(str(row[item.column]).replace('Z', '+00:00')) >= item.value]
            else:
                raise AssertionError(item)
        for item in reversed(order):
            rows.sort(key=lambda row: str(row.get(item.column) or ''), reverse=item.descending)
        return rows[offset:offset + limit]

    def rpc(self, *args, **kwargs):
        raise AssertionError('RPC forbidden')

    def insert(self, *args, **kwargs):
        raise AssertionError('write forbidden')


@pytest.fixture
def canonical(completed):
    order, outcome, payment, event = records(completed)
    order['prospect_id'] = PROSPECT
    event['idempotency_key'] = f'revenue:{ORDER}:v1'
    causal = lineage(completed)
    intent = dict(id=INTENT, prospect_id=PROSPECT, buyer_id=order['buyer_id'], opportunity_id=OPPORTUNITY,
        offer_key='managed_service', status='replied', created_at=THEN, updated_at=THEN,
        metadata={'causal_lineage': causal, 'department_work_id': completed['id'],
                  'opportunity_key': causal['opportunity_key'], 'adaptive_outreach': {
                      'subject_arm': 'a', 'body_arm': 'a', 'exact_segment': 'managed_service|roofing|owner'}})
    case = dict(id=CASE, outbound_intent_id=INTENT, reply_id=REPLY, prospect_id=PROSPECT,
        buyer_id=order['buyer_id'], opportunity_id=OPPORTUNITY, fulfilment_order_id=ORDER, opened_at=THEN)
    reply = dict(id=REPLY, intent_id=INTENT, classification='positive', received_at=THEN)
    conversation = dict(id='conversation-1', outbound_intent_id=INTENT, prospect_id=PROSPECT,
        buyer_id=order['buyer_id'], opportunity_id=OPPORTUNITY, closer_case_id=CASE)
    tables = {'outbound_intents': [intent], 'closer_cases': [case], 'outbound_replies': [reply],
        'empire_conversations': [conversation], 'prospects': [{'id': PROSPECT}],
        'gtm_opportunities': [{'id': OPPORTUNITY}], 'fulfilment_orders': [order],
        'buyers': [{'id': order['buyer_id'], 'org_id': TENANT}], 'commercial_outcomes': [outcome],
        'commercial_events': [event], 'bsc_payment_evidence': [payment],
        'bsc_payment_requests': [dict(id='request-1', fulfilment_order_id=ORDER, status='approved',
            approved_at=THEN, approved_by='offline-founder', commercial_terms_sha256='b'*64,
            amount_usdt='100', settlement_mode='direct')]}
    return Gateway(tables)


def bridge(gateway, tmp_path, record=None):
    intent = gateway.tables['outbound_intents'][0]
    raw = record or dict(intent_id=str(intent['id']), outbound_intent_id=str(intent['id']),
        metadata=deepcopy(intent['metadata']), delivered=True, classification='positive')
    return ExecutionBusDataRepository(gateway).outreach_verified_outcome_record(raw, repo_root=tmp_path, as_of=NOW)


def snapshot(rows):
    return build_performance_snapshot(rows, generated_at=NOW.isoformat())


def revenue(payload):
    return payload['segments']['__global__']['body_arms']['a']['recognized_revenue']


def produce(gateway, tmp_path):
    return ExecutionBusDataRepository(gateway).outreach_performance_records(lookback_days=90, repo_root=tmp_path, as_of=NOW)


def test_explicit_canonical_path_reaches_existing_validator_and_optimizer(canonical, tmp_path):
    result = bridge(canonical, tmp_path)
    feedback = result['verified_outcome_feedback']
    validate_verified_feedback(feedback, tenant_id=TENANT, as_of=NOW)
    assert result['outcome_bridge_state'] == 'VERIFIED'
    assert result['outbound_intent_id'] == INTENT
    assert result['prospect_id'] == PROSPECT and result['buyer_id'] == 'buyer-1'
    assert result['opportunity_id'] == OPPORTUNITY and result['fulfilment_order_id'] == ORDER
    assert result['outcome_ref'] == feedback['outcome_ref']
    assert result['outreach_outcome_attribution']['execution_ref'] == feedback['execution_ref']
    assert feedback['execution_authority'] == 'none'
    assert revenue(snapshot([result])) == 1
    assert snapshot([result])['winner_claim_allowed'] is False


def test_actual_refresh_read_boundary_uses_existing_repository(canonical, completed, tmp_path, monkeypatch):
    import empire_os.data_backends.empiredb as backend
    events = []
    class Provider:
        @contextmanager
        def read_only_snapshot(self):
            events.append('read_only_enter')
            yield canonical
            events.append('read_only_exit')
    monkeypatch.setattr(backend, 'EmpireDbProvider', lambda connector: Provider())
    payload = runtime.refresh(tmp_path, dsn='postgresql://offline-unused', now=NOW)
    assert events == ['read_only_enter', 'read_only_exit']
    assert payload['outcome_bridge']['states'] == {'VERIFIED': 1}
    assert revenue(payload) == 1
    assert payload['execution_authority'] == 'none'
    assert payload['outbound_mutation'] is False
    assert (tmp_path / runtime.SNAPSHOT_PATH).is_file()
    assert all(columns == '*' for table, columns, _ in canonical.queries if table in ('commercial_outcomes', 'commercial_events'))


@pytest.mark.parametrize('part', ['positive_only', 'order_only', 'payment_only', 'missing_recognition',
    'synthetic', 'forecast', 'unverified', 'future_outcome', 'future_payment', 'future_recognition',
    'future_link', 'tenant', 'order_tenant', 'outcome_tenant', 'reply_intent', 'case_intent',
    'intent_prospect', 'order_prospect', 'buyer', 'opportunity', 'order_link', 'outcome_order',
    'execution', 'missing_causal', 'shadow_causal', 'outcome_execution', 'future_work', 'missing_work',
    'missing_prediction_link', 'conversation_prospect', 'conversation_buyer', 'conversation_case',
    'ambiguous_case', 'ambiguous_conversation'])
def test_missing_contradictory_or_unverified_links_fail_closed(canonical, completed, tmp_path, part):
    t = canonical.tables
    if part == 'positive_only': t['closer_cases'] = []
    if part == 'order_only': t['commercial_outcomes'] = []; t['commercial_events'] = []; t['bsc_payment_evidence'] = []
    if part == 'payment_only': t['commercial_outcomes'] = []; t['commercial_events'] = []
    if part == 'missing_recognition': t['commercial_events'] = []
    if part == 'synthetic': t['commercial_outcomes'][0]['synthetic'] = True
    if part == 'forecast': t['commercial_outcomes'][0]['forecast_derived'] = True
    if part == 'unverified': t['commercial_outcomes'][0]['verified'] = False
    if part == 'future_outcome': t['commercial_outcomes'][0]['recorded_at'] = '2099-01-01T00:00:00Z'
    if part == 'future_payment': t['bsc_payment_evidence'][0]['verified_at'] = '2099-01-01T00:00:00Z'
    if part == 'future_recognition': t['commercial_events'][0]['occurred_at'] = '2099-01-01T00:00:00Z'
    if part == 'future_link': t['closer_cases'][0]['updated_at'] = '2099-01-01T00:00:00Z'
    if part == 'tenant': t['buyers'][0]['org_id'] = 'wrong'
    if part == 'order_tenant': t['fulfilment_orders'][0]['tenant_id'] = 'wrong'
    if part == 'outcome_tenant': t['commercial_outcomes'][0]['tenant_id'] = 'wrong'
    if part == 'reply_intent': t['outbound_replies'][0]['intent_id'] = 'wrong'
    if part == 'case_intent': t['closer_cases'][0]['outbound_intent_id'] = 'wrong'
    if part == 'intent_prospect': t['outbound_intents'][0]['prospect_id'] = 'wrong'
    if part == 'order_prospect': t['fulfilment_orders'][0]['prospect_id'] = 'wrong'
    if part == 'buyer': t['closer_cases'][0]['buyer_id'] = 'wrong'
    if part == 'opportunity': t['closer_cases'][0]['opportunity_id'] = 'wrong'
    if part == 'order_link': t['closer_cases'][0]['fulfilment_order_id'] = 'wrong'
    if part == 'outcome_order': t['commercial_outcomes'][0]['fulfilment_order_id'] = 'wrong'
    if part == 'execution': t['outbound_intents'][0]['metadata']['causal_lineage']['execution_ref'] = 'department_work:wrong'
    if part == 'missing_causal': t['outbound_intents'][0]['metadata'].pop('causal_lineage')
    if part == 'shadow_causal': t['fulfilment_orders'][0]['commercial_payload']['causal_lineage']['causal_eligible'] = False
    if part == 'outcome_execution': t['commercial_outcomes'][0]['evidence']['causal_lineage']['execution_ref'] = 'department_work:wrong'
    if part in ('future_work', 'missing_work'):
        import json
        path = tmp_path / 'runtime/departments/work/done' / (completed['id'] + '.json')
        data = json.loads(path.read_text())
        data['updated_at'] = '2099-01-01T00:00:00Z' if part == 'future_work' else data['updated_at']
        if part == 'missing_work': data['status'] = 'BLOCKED'
        path.write_text(json.dumps(data))
    if part == 'missing_prediction_link': t['outbound_intents'][0]['metadata'].pop('department_work_id')
    if part == 'conversation_prospect': t['empire_conversations'][0]['prospect_id'] = 'wrong'
    if part == 'conversation_buyer': t['empire_conversations'][0]['buyer_id'] = 'wrong'
    if part == 'conversation_case': t['empire_conversations'][0]['closer_case_id'] = 'wrong'
    if part == 'ambiguous_case': t['closer_cases'].append(deepcopy(t['closer_cases'][0]))
    if part == 'ambiguous_conversation': t['empire_conversations'].append(deepcopy(t['empire_conversations'][0]))
    rows = produce(canonical, tmp_path)
    assert rows[0]['outcome_bridge_state'] == 'UNKNOWN'
    assert 'verified_outcome_feedback' not in rows[0]
    assert revenue(snapshot(rows)) == 0


@pytest.mark.parametrize('key', ['outbound_intent_id', 'tenant_id', 'prospect_id', 'buyer_id',
    'opportunity_id', 'fulfilment_order_id', 'outcome_ref', 'prediction_ref', 'decision_ref', 'execution_ref'])
def test_caller_cannot_override_canonical_lineage(canonical, tmp_path, key):
    raw = dict(intent_id=INTENT, metadata=deepcopy(canonical.tables['outbound_intents'][0]['metadata']), **{key: 'wrong'})
    with pytest.raises(ValueError): bridge(canonical, tmp_path, raw)


def test_names_email_and_time_proximity_are_not_attribution(canonical, tmp_path):
    canonical.tables['closer_cases'][0]['outbound_intent_id'] = 'another-intent'
    for table in ('closer_cases', 'fulfilment_orders', 'outbound_intents'):
        canonical.tables[table][0].update(email='same@example.com', business_name='Same company', created_at=THEN)
    rows = produce(canonical, tmp_path)
    assert revenue(snapshot(rows)) == 0
    assert all(item.column not in ('email', 'business_name', 'recipient') for _, _, filters in canonical.queries for item in filters)


def test_one_canonical_outcome_ref_cannot_be_counted_twice(canonical, tmp_path):
    first = bridge(canonical, tmp_path)
    other = deepcopy(first)
    other['intent_id'] = 'distinct-intent'
    other['metadata']['adaptive_outreach']['body_arm'] = 'b'
    result = snapshot([first, first, other])
    global_arms = result['segments']['__global__']['body_arms']
    assert sum(row['recognized_revenue'] for row in global_arms.values()) == 1


def test_existing_validator_remains_required_at_both_boundaries(canonical, tmp_path, monkeypatch):
    import empire_os.outcome_feedback as feedback
    original = feedback.validate_verified_feedback
    calls = []
    def validate(row, **kwargs):
        calls.append(row['outcome_ref'])
        return original(row, **kwargs)
    monkeypatch.setattr(feedback, 'validate_verified_feedback', validate)
    record = bridge(canonical, tmp_path)
    assert revenue(snapshot([record])) == 1 and len(calls) == 2
    record['verified_outcome_feedback']['cortex_packet']['verification']['recognized_revenue'] = False
    assert revenue(snapshot([record])) == 0


def test_absent_conversation_is_not_fabricated_when_direct_case_fk_exists(canonical, tmp_path):
    canonical.tables['empire_conversations'] = []
    result = bridge(canonical, tmp_path)
    assert result['outreach_outcome_attribution']['conversation_id'] is None
    assert revenue(snapshot([result])) == 1


def test_unknown_funnel_stages_and_suppression_remain_explicit(canonical, tmp_path):
    result = bridge(canonical, tmp_path)
    result['classification'] = 'unsubscribe'
    payload = snapshot([result])
    assert payload['unavailable_stage_sources'] == []
    assert set(payload['middle_stage_sources']) == {'qualified_conversation', 'commercial_terms'}
    arm = payload['segments']['__global__']['body_arms']['a']
    assert arm['qualified_conversation'] == arm['commercial_terms'] == 0
    assert arm['unsubscribes'] == 1 and arm['commercial_replies'] == 0
    assert classify_reply_text('unsubscribe')['classification'] == 'unsubscribe'
    assert payload['execution_authority'] == 'none'


def test_verified_revenue_cannot_bypass_sample_or_exploration_safeguards(canonical, tmp_path):
    payload = snapshot([bridge(canonical, tmp_path)])
    assert not payload['winner_claim_allowed']
    assert (MIN_DELIVERED_PER_ARM, SEGMENT_MIN_DELIVERED, EXPLORATION_FRACTION) == (8, 16, .20)
    mature = {'segments': {'__global__': {'delivered': 16, **{
        group: {'a': {'delivered': 8, 'commercial_replies': 1, 'recognized_revenue': 999},
                'b': {'delivered': 8, 'commercial_replies': 2}}
        for group in ('subject_arms', 'body_arms')}}}}
    key = next(str(i) for i in range(1000) if _bucket(f'explore:body_arms:{i}') < 2000)
    selection = select_message_arms(assignment_key=key, subject_arm_ids=('a','b'), body_arm_ids=('a','b'),
        offer_key='offer', niche='roofing', decision_role='owner', snapshot=mature)
    assert selection['body_selection']['exploration'] is True
    assert selection['execution_authority'] == 'copy_selection_only'


def test_native_postgres_uuid_timestamp_records_cross_existing_feedback_boundary(canonical, tmp_path):
    for rows in canonical.tables.values():
        for row in rows:
            for key, value in list(row.items()):
                if key == 'id' or key.endswith('_id'):
                    try: row[key] = UUID(value)
                    except (ValueError, TypeError): pass
                if key.endswith('_at') and isinstance(value, str):
                    row[key] = datetime.fromisoformat(value.replace('Z', '+00:00'))
    result = bridge(canonical, tmp_path)
    assert revenue(snapshot([result])) == 1
    assert result['fulfilment_order_id'] == ORDER


def test_read_only_snapshot_reuses_connection_and_rolls_back_without_commit():
    connection = FakeConnection()
    connection.next_cursor = Cursor([('one',)], ('id',))
    provider = EmpireDbProvider(FakeConnector(connection))
    with provider.read_only_snapshot() as reader:
        assert reader.query('prospects', 'id') == [{'id': 'one'}]
        assert reader.query('prospects', 'id') == [{'id': 'one'}]
        assert not connection.closed and connection.commits == 0
    assert connection.closed and connection.commits == 0 and connection.rollbacks == 2
    assert 'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY' in [sql for sql, _ in connection.calls]
    with pytest.raises(RuntimeError): reader.query('prospects', 'id')


@pytest.mark.parametrize('method', ['insert', 'upsert', 'update', 'delete', 'insert_ignore_conflicts', 'rpc', 'transaction'])
def test_read_only_snapshot_has_no_write_or_rpc_surface(method):
    connection = FakeConnection()
    with EmpireDbProvider(FakeConnector(connection)).read_only_snapshot() as reader:
        with pytest.raises(DataGatewayOperationUnsupported): getattr(reader, method)('forbidden')
    assert not any(sql.startswith(('INSERT', 'UPDATE', 'DELETE', 'SELECT')) for sql, _ in connection.calls)
    assert connection.commits == 0


def test_unlabelled_intents_never_receive_commercial_credit(canonical, tmp_path):
    canonical.tables['outbound_intents'][0]['metadata'].pop('adaptive_outreach')
    rows = produce(canonical, tmp_path)
    assert rows[0]['outcome_bridge_state'] == 'UNLABELLED'
    assert 'verified_outcome_feedback' not in rows[0]
    assert all(table not in ('closer_cases', 'commercial_outcomes') for table, _, _ in canonical.queries)


def test_corrupted_verified_feedback_is_rejected_by_repository_validator(canonical, tmp_path, monkeypatch):
    repository = ExecutionBusDataRepository(canonical)
    result = bridge(canonical, tmp_path)
    feedback = deepcopy(result['verified_outcome_feedback'])
    feedback['cortex_packet']['verification']['recognized_revenue'] = False
    monkeypatch.setattr(repository, 'verified_outcome_feedback', lambda *args, **kwargs: feedback)
    intent = canonical.tables['outbound_intents'][0]
    raw = dict(intent_id=INTENT, metadata=intent['metadata'])
    with pytest.raises(ValueError, match='recognized revenue'):
        repository.outreach_verified_outcome_record(raw, repo_root=tmp_path, as_of=NOW)


def test_swallowed_sql_failure_cannot_publish_a_partial_read_snapshot():
    class FailedConnection(FakeConnection):
        def execute(self, sql, params=()):
            if sql.startswith('SELECT'): raise RuntimeError('offline failed read')
            return super().execute(sql, params)
    connection = FailedConnection()
    with pytest.raises(RuntimeError, match='transaction has failed'):
        with EmpireDbProvider(FakeConnector(connection)).read_only_snapshot() as reader:
            with pytest.raises(RuntimeError, match='offline failed read'):
                reader.query('prospects', 'id')
    assert not connection.commits and connection.closed


def test_bridge_preserves_original_record_and_does_not_trust_injected_feedback(canonical, tmp_path):
    intent = canonical.tables['outbound_intents'][0]
    raw = dict(intent_id=INTENT, metadata=deepcopy(intent['metadata']),
               verified_outcome_feedback={'actual_revenue': True, 'actual_revenue_cents': 999999})
    original = deepcopy(raw)
    result = bridge(canonical, tmp_path, raw)
    assert raw == original
    assert result['verified_outcome_feedback']['actual_revenue_cents'] == 10000
    assert result['outreach_outcome_attribution']['execution_authority'] == 'none'


def test_record_read_errors_abort_instead_of_publishing_unknown_revenue(canonical, tmp_path, monkeypatch):
    original = canonical.query
    def query(table, *args, **kwargs):
        if table == 'bsc_payment_evidence': raise ConnectionError('offline connection failure')
        return original(table, *args, **kwargs)
    monkeypatch.setattr(canonical, 'query', query)
    with pytest.raises(ConnectionError): produce(canonical, tmp_path)


@pytest.mark.parametrize('key', ['outbound_intent_id', 'prospect_id', 'buyer_id', 'opportunity_id',
                                 'fulfilment_order_id', 'outcome_ref'])
def test_canonical_metadata_cannot_contradict_canonical_relationships(canonical, tmp_path, key):
    canonical.tables['outbound_intents'][0]['metadata'][key] = 'wrong'
    rows = produce(canonical, tmp_path)
    assert rows[0]['outcome_bridge_state'] == 'UNKNOWN'
    assert revenue(snapshot(rows)) == 0
