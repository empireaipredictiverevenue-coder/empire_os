from empire_os.commercial_loop_observer import CommercialLoopObservation as Obs, assess_commercial_loop
from empire_os.commercial_loop_refresh_contract import preserve_cycle_local_observations


def test_missing_local_evidence_remains_unknown():
    merged = preserve_cycle_local_observations({}, {'buyer_conversation': Obs('buyer_conversation', False)})
    status = assess_commercial_loop({'real_acquisition': Obs('real_acquisition', True), **merged})
    assert status.highest_priority_blocker == 'qualification_v2'
    assert status.blocker_state == 'unknown'
    assert merged['omega_projection'].observed is None


def test_existing_cycle_local_evidence_preserved():
    existing = {'qualification_v2': Obs('qualification_v2', True), 'omega_projection': Obs('omega_projection', False)}
    merged = preserve_cycle_local_observations(existing, {'qualification_v2': Obs('qualification_v2', False)})
    assert merged['qualification_v2'].observed is True
    assert merged['omega_projection'].observed is False


def test_unknown_local_evidence_not_upgraded_by_refresh():
    existing = {'qualification_v2': Obs('qualification_v2', None)}
    merged = preserve_cycle_local_observations(existing, {})
    assert merged['qualification_v2'].observed is None
    assert 'qualification cycle required' in merged['qualification_v2'].detail
