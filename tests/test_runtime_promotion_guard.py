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
