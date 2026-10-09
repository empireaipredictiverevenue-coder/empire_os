import json
import pytest
from empire_os.commercial_loop_reader import CommercialLoopReadError, read_commercial_loop


def test_valid_observe_snapshot(tmp_path):
    p = tmp_path / 'latest.json'
    p.write_text(json.dumps({'mode':'OBSERVE','execution_authority':'none','stages':[]}))
    assert read_commercial_loop(p)['stages'] == []


def test_missing_snapshot_fails_closed(tmp_path):
    with pytest.raises(CommercialLoopReadError, match='snapshot_unavailable'):
        read_commercial_loop(tmp_path / 'missing.json')


@pytest.mark.parametrize('payload', [[], {'mode':'OBSERVE','execution_authority':'none'}, {'mode':'EXECUTE','execution_authority':'none','stages':[]}, {'mode':'OBSERVE','execution_authority':'send','stages':[]}])
def test_invalid_snapshot_fails_closed(tmp_path, payload):
    p = tmp_path / 'latest.json'
    p.write_text(json.dumps(payload))
    with pytest.raises(CommercialLoopReadError, match='snapshot_invalid'):
        read_commercial_loop(p)
