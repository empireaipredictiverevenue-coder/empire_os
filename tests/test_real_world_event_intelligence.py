from dataclasses import replace
from datetime import datetime, timezone
import json
import pytest

from empire_os.real_world_event_intelligence import (
    canonical_evidence_hash, assess_event_truth, normalized_event_evidence,
    replay_source_evidence, PhysicalEventTruth, AUTHORITY_FIELDS,
)
from empire_os.spatial_physical_adapters import event_evidence_from_storm_event, physical_from_storm_event
from empire_os.storm_predictor import StormEvent
from empire_os.storm_service import StormService
from empire_os.storm_intelligence_runtime import materialize_storm_intelligence

NOW = datetime(2026, 10, 5, 10, tzinfo=timezone.utc)

def event(**raw):
    props = dict(sent='2026-10-05T09:00:00Z', expires='2026-10-05T11:00:00Z',
                 certainty='Observed', severity='Severe', status='Actual',
                 messageType='Alert', category='Met', urgency='Immediate',
                 event='Tornado Warning', areaDesc='Test County',
                 parameters={'VTEC': ['test-vtec'], 'NWSheadline': ['Test headline']})
    props.update(raw)
    return StormEvent(event_id='nws:1', event_type='Tornado Warning', severity=4,
                      area_description='Test County', raw=props, retrieved_at=NOW.isoformat())

def evidence(**raw):
    return event_evidence_from_storm_event(event(**raw))

@pytest.mark.parametrize('certainty,expected', [('Observed','OBSERVED'),('Likely','LIKELY'),('Possible','POSSIBLE'),('other',None)])
def test_assertions_are_not_physical_truth(certainty, expected):
    row = normalized_event_evidence(evidence(certainty=certainty))
    assert row['source_truth'] == 'OBSERVED_SOURCE_RECORD'
    assert row['assertion_truth'] == ('SOURCE_REPORTS_' + expected if expected else 'SOURCE_UNKNOWN')
    assert row['physical_truth'] == 'UNKNOWN'

@pytest.mark.parametrize('value,reason', [(None,'missing'),('broken','invalid'),('2026-10-05T09:00:00','timezone_missing')])
def test_bad_source_times_fail_closed(value, reason):
    with pytest.raises(ValueError, match='source_timestamp_' + reason):
        StormService._canonical_event_row(event(sent=value))

@pytest.mark.parametrize('field', ['effective', 'onset', 'expires', 'ends'])
def test_optional_malformed_timestamps_are_not_ignored(field):
    with pytest.raises(ValueError, match='source_timestamp_invalid'):
        evidence(**{field: 'broken'})

def test_canonical_hash_and_normalization():
    assert canonical_evidence_hash({'a':1,'b':{'x':2,'y':3}}) == canonical_evidence_hash({'b':{'y':3,'x':2},'a':1})
    assert canonical_evidence_hash({'a':1}) != canonical_evidence_hash({'a':2})
    first = evidence()
    reordered = event()
    reordered.raw = dict(reversed(list(reordered.raw.items())))
    assert normalized_event_evidence(first) == normalized_event_evidence(event_evidence_from_storm_event(reordered))
    assert first.raw_evidence_hash != evidence(certainty='Likely').raw_evidence_hash

@pytest.mark.parametrize('truth', [PhysicalEventTruth.CORROBORATED, PhysicalEventTruth.VERIFIED])
def test_single_source_cannot_promote(truth):
    assessment = assess_event_truth((evidence(), evidence()))
    assert assessment.source_count == assessment.independent_source_count == 1
    with pytest.raises(ValueError, match='verification pipeline'):
        replace(assessment, physical_truth=truth)

def test_conflicts_visible_and_duplicates_not_independent():
    assessment = assess_event_truth((evidence(), evidence(certainty='Possible')))
    assert assessment.conflict_state == 'CONFLICTING_SOURCE_ASSERTIONS'
    assert assessment.physical_truth == PhysicalEventTruth.UNKNOWN
    assert assessment.independent_source_count == 1

@pytest.mark.parametrize('authority', AUTHORITY_FIELDS)
def test_authority_none( authority):
    assessment = assess_event_truth((evidence(),))
    assert getattr(assessment, authority) == 'none'
    with pytest.raises(ValueError, match='authority'):
        replace(assessment, **{authority: 'execute'})

@pytest.mark.parametrize('claim', ['property_damage','business_damage','buyer_intent','confirmed_demand','revenue'])
def test_alert_does_not_claim_consequences(claim):
    row = normalized_event_evidence(evidence())
    assert claim not in row
    physical = physical_from_storm_event(event())
    assert physical.physical_truth == 'UNKNOWN'
    assert physical.phenomenon == 'storm_exposure'
    assert physical.measurements == {}

def test_persisted_evidence_replay_dedupe_and_conflict(tmp_path):
    first = StormService._canonical_event_row(event())
    changed = StormService._canonical_event_row(event(certainty='Possible'))
    snapshot = materialize_storm_intelligence(tmp_path, events=[first,first,changed], now=NOW)
    persisted = json.loads((tmp_path/'runtime/storm_opportunity/latest.json').read_text())
    rows = persisted['event_truth']['evidence']
    assert len(rows) == 2
    assert [normalized_event_evidence(replay_source_evidence(row)) for row in rows] == rows
    assert persisted['event_truth']['assessments'][0]['conflict_state'] == 'CONFLICTING_SOURCE_ASSERTIONS'
    assert snapshot['candidate_count'] == 0

def test_malformed_batch_isolation(monkeypatch, tmp_path):
    from types import SimpleNamespace
    import empire_os.storm_service as module
    service = object.__new__(StormService)
    good2 = event(); good2.event_id = 'nws:2'
    batch = [event(), event(sent='bad'), good2]
    service.predictor = SimpleNamespace(events=batch, scan=lambda: batch)
    monkeypatch.setattr(module, 'REPO_ROOT', tmp_path)
    _, snapshot = service._scan_and_materialize()
    assert snapshot['diagnostics']['events_valid'] == 2
    assert snapshot['event_truth']['rejections'] == [{'index':1,'reason':'source_timestamp_invalid'}]
    assert len(snapshot['event_truth']['evidence']) == 2

def test_bounded_retention_and_no_raw_secrets(tmp_path):
    rows = []
    for index in range(105):
        item = event(secret_token='DO_NOT_RETAIN'); item.event_id = f'nws:{index:03}'
        rows.append(StormService._canonical_event_row(item))
    snapshot = materialize_storm_intelligence(tmp_path, events=rows, now=NOW)
    assert len(snapshot['event_truth']['evidence']) == 100
    assert snapshot['event_truth']['omitted_count'] == 5
    assert 'DO_NOT_RETAIN' not in json.dumps(snapshot)

def test_replay_rejects_tampering():
    row = normalized_event_evidence(evidence())
    row['certainty'] = 'Likely'
    with pytest.raises(ValueError, match='evidence_hash_mismatch'):
        replay_source_evidence(row)

def test_predictor_isolates_malformed_source_records(monkeypatch):
    from unittest.mock import MagicMock
    from empire_os.storm_predictor import StormPredictor
    valid = {'id': 'a', 'properties': event().raw}
    payload = {'features': [valid, {'id':'bad','properties':event(sent='bad').raw},
                            {'id':'b','properties':event().raw}, {'properties':{'event':[]}}]}
    response = MagicMock()
    response.__enter__.return_value = response
    response.read.return_value = json.dumps(payload).encode()
    monkeypatch.setattr('urllib.request.urlopen', lambda *a, **k: response)
    predictor = StormPredictor()
    monkeypatch.setattr(predictor, '_notify', lambda e: None)
    assert len(predictor.scan()) == 2
    assert [r['reason'] for r in predictor.rejections] == ['source_timestamp_invalid','source_field_invalid']

def test_conflict_cannot_be_resurrected_by_third_copy(tmp_path):
    from tests.test_storm_intelligence_runtime import event as runtime_event
    snapshot = materialize_storm_intelligence(tmp_path, events=[runtime_event(), runtime_event(severity='extreme'), runtime_event()], now=NOW)
    assert snapshot['diagnostics']['events_valid'] == 0

def test_separate_nws_records_are_not_independent():
    second = event(); second.event_id = 'nws:copy'
    assessment = assess_event_truth((evidence(), event_evidence_from_storm_event(second)))
    assert assessment.source_count == 2
    assert assessment.independent_source_count == 1
    assert assessment.physical_truth == PhysicalEventTruth.UNKNOWN

def test_source_forecast_remains_source_assertion():
    assert normalized_event_evidence(evidence(certainty=None, messageType='Forecast'))['assertion_truth'] == 'SOURCE_FORECAST'

@pytest.mark.parametrize('authority', AUTHORITY_FIELDS)
def test_source_and_assertion_cannot_grant_authority(authority):
    source = evidence()
    assertion = assess_event_truth((source,)).assertion
    for item in (source, assertion):
        with pytest.raises(ValueError, match='authority'):
            replace(item, **{authority: 'execute'})
