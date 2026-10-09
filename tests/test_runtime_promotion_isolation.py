"""Execute promotion entrypoints against disposable fixtures, never live bindings."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LANES = {
    'leads': ('promote_leads_runtime_bindings.py', 'runtime/leads_control/leads_runtime_observer_latest.json'),
    'campaigns': ('promote_campaign_runtime_bindings.py', 'runtime/campaigns_control/campaign_runtime_observer_latest.json'),
}
BINDINGS = 'runtime/control_plane/runtime_control_bindings_latest.json'


def run_isolated(tmp_path, lane, change):
    script, proof_path = LANES[lane]
    for rel in (BINDINGS, proof_path):
        src = ROOT / rel
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())
    proof = tmp_path / proof_path
    obj = json.loads(proof.read_text())
    change(obj)
    proof.write_text(json.dumps(obj))
    source = (ROOT / 'scripts' / script).read_text()
    assert 'ROOT = Path("/srv/empire_os")' in source
    source = source.replace('ROOT = Path("/srv/empire_os")', f'ROOT = Path({str(tmp_path)!r})', 1)
    staged = tmp_path / script
    staged.write_text(source)
    binding = tmp_path / BINDINGS
    before = binding.read_bytes()
    env = {**os.environ, 'PYTHONPATH': str(ROOT)}
    result = subprocess.run([sys.executable, str(staged)], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=15)
    return result, before, binding.read_bytes()


@pytest.mark.parametrize('lane', LANES)
@pytest.mark.parametrize('change', [
    lambda d: d.update(generated_at='2020-01-01T00:00:00+00:00'),
    lambda d: d.update(generated_at='invalid'),
    lambda d: d.update(mode='EXECUTE'),
    lambda d: d.update(outbound=True),
    lambda d: d.update(db_write=True),
    lambda d: d.update(action_authority_granted=True),
    lambda d: d.update(lane='wrong_lane'),
    lambda d: d.update(runtime_verified_controls=['unapproved_control']),
])
def test_rejected_proof_never_changes_bindings(tmp_path, lane, change):
    result, before, after = run_isolated(tmp_path, lane, change)
    assert result.returncode != 0, result.stdout
    assert after == before


@pytest.mark.parametrize('lane', LANES)
def test_valid_proof_never_touches_production(tmp_path, lane):
    production_before = (ROOT / BINDINGS).read_bytes()
    result, _, _ = run_isolated(tmp_path, lane, lambda d: None)
    assert (ROOT / BINDINGS).read_bytes() == production_before
    assert result.returncode == 0, result.stderr + result.stdout
