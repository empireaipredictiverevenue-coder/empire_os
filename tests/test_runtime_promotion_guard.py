from datetime import datetime, timezone, timedelta
import pytest
from empire_os.runtime_promotion_guard import validate_control_proof, PromotionProofError

NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)


def proof():
    return {'lane': 'leads', 'mode': 'OBSERVE', 'status': 'VERIFIED_RUNTIME', 'generated_at': NOW.isoformat(), 'runtime_verified_controls': ['input_quality']}


def test_valid_observe_proof():
    assert validate_control_proof(proof(), lane='leads', allowed={'input_quality'}, now=NOW) == {'input_quality'}


@pytest.mark.parametrize('patch', [
    {'lane': 'other'}, {'mode': 'EXECUTE'}, {'status': 'NO_RUNTIME_PROOF'},
    {'generated_at': (NOW - timedelta(days=8)).isoformat()},
    {'generated_at': (NOW + timedelta(seconds=1)).isoformat()},
    {'generated_at': 'not-a-date'}, {'generated_at': '2026-10-09T00:00:00'},
    {'runtime_verified_controls': []}, {'runtime_verified_controls': ['action_authority']},
    {'runtime_verified_controls': ['input_quality', 'input_quality']},
    {'db_write': True}, {'outbound': True}, {'action_authority_granted': True},
    {'campaign_state_mutated': True},
])
def test_fail_closed(patch):
    with pytest.raises(PromotionProofError):
        validate_control_proof({**proof(), **patch}, lane='leads', allowed={'input_quality'}, now=NOW)


def test_campaign_observer_allows_authority_control_as_evidence_only():
    campaign = {**proof(), 'lane': 'campaigns', 'runtime_verified_controls': ['input_quality', 'action_authority']}
    verified = validate_control_proof(campaign, lane='campaigns', allowed={'input_quality', 'action_authority'}, now=NOW)
    assert verified & {'input_quality'} == {'input_quality'}
    assert 'action_authority' in verified  # This is an observed control, not an execution grant.


@pytest.mark.parametrize('flag', ['outbound', 'db_write', 'action_authority_granted', 'campaign_state_mutated'])
def test_campaign_rejects_consequential_execution_even_with_authority_control(flag):
    campaign = {**proof(), 'lane': 'campaigns', 'runtime_verified_controls': ['input_quality', 'action_authority'], flag: True}
    with pytest.raises(PromotionProofError):
        validate_control_proof(campaign, lane='campaigns', allowed={'input_quality', 'action_authority'}, now=NOW)


def test_atomic_binding_write_rejects_changed_source(tmp_path):
    from empire_os.runtime_promotion_guard import atomic_binding_write, PromotionWriteError
    p = tmp_path / 'bindings.json'
    p.write_text('newer')
    with pytest.raises(PromotionWriteError, match='changed'):
        atomic_binding_write(p, 'old', expected_bytes=b'original')
    assert p.read_text() == 'newer'
    assert not list(tmp_path.glob('*.tmp'))


def test_atomic_binding_write_success(tmp_path):
    from empire_os.runtime_promotion_guard import atomic_binding_write
    p = tmp_path / 'bindings.json'
    p.write_text('old')
    atomic_binding_write(p, 'new', expected_bytes=b'old')
    assert p.read_text() == 'new'


def test_binding_writer_lock_is_reentrant_across_sequential_calls(tmp_path):
    from empire_os.runtime_promotion_guard import binding_writer_lock
    path = tmp_path / 'bindings.json'
    with binding_writer_lock(path):
        path.write_text('first')
    with binding_writer_lock(path):
        path.write_text('second')
    assert path.read_text() == 'second'
