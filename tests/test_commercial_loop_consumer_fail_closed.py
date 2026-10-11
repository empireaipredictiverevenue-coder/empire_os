import importlib.util
from pathlib import Path


def test_revenue_pulse_missing_snapshot_fails_closed(tmp_path):
    script = Path(__file__).resolve().parents[1] / 'scripts/build_revenue_pulse_snapshot.py'
    spec = importlib.util.spec_from_file_location('pulse_snapshot_contract_test', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT = tmp_path
    blocker, state = module.load_commercial_blocker()
    assert blocker == 'commercial_loop_snapshot_unreadable'
    assert state.startswith('snapshot_unavailable:')
