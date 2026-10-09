"""Run legacy binding writers against disposable files only."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BINDINGS = 'runtime/control_plane/runtime_control_bindings_latest.json'
SCRIPTS = (
    'promote_campaign_final_bindings',
    'promote_campaign_measured_controls',
    'promote_opportunities_final_bindings',
    'reconcile_materialized_runtime_bindings',
)


@pytest.mark.parametrize('name', SCRIPTS)
@pytest.mark.parametrize('binding_data', [b'{invalid-json', b'{"lanes": []}'])
def test_legacy_writer_fails_closed_on_bad_bindings(tmp_path, name, binding_data):
    target = tmp_path / BINDINGS
    target.parent.mkdir(parents=True)
    target.write_bytes(binding_data)
    source = (ROOT / 'scripts' / (name + '.py')).read_text()
    assert 'ROOT = Path("/srv/empire_os")' in source
    source = source.replace('ROOT = Path("/srv/empire_os")', f'ROOT = Path({str(tmp_path)!r})', 1)
    staged = tmp_path / (name + '.py')
    staged.write_text(source)
    before = target.read_bytes()
    env = {**os.environ, 'PYTHONPATH': str(ROOT)}
    result = subprocess.run([sys.executable, str(staged)], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=15)
    assert result.returncode != 0
    assert target.read_bytes() == before
    assert not list(target.parent.glob('*.tmp*'))


@pytest.mark.parametrize('name', SCRIPTS)
def test_legacy_writer_never_uses_production_binding_path(tmp_path, name):
    """A missing local proof must fail without touching any live file."""
    target = tmp_path / BINDINGS
    target.parent.mkdir(parents=True)
    target.write_bytes((ROOT / BINDINGS).read_bytes())
    source = (ROOT / 'scripts' / (name + '.py')).read_text()
    assert 'ROOT = Path("/srv/empire_os")' in source
    staged = tmp_path / (name + '.py')
    staged.write_text(source.replace('ROOT = Path("/srv/empire_os")', f'ROOT = Path({str(tmp_path)!r})', 1))
    before = target.read_bytes()
    result = subprocess.run([sys.executable, str(staged)], cwd=tmp_path,
                            env={**os.environ, 'PYTHONPATH': str(ROOT)},
                            capture_output=True, text=True, timeout=15)
    assert result.returncode != 0
    assert target.read_bytes() == before


@pytest.mark.parametrize('name,lane,controls', [
    ('promote_campaign_measured_controls', 'campaigns', ('output_quality',)),
    ('promote_opportunities_final_bindings', 'opportunities', ('entity_classification', 'quarantine', 'outcome_linkage')),
])
def test_legacy_writer_successful_isolated_promotion(tmp_path, name, lane, controls):
    """Exercise a complete synthetic successful write, without a live promotion."""
    import json
    target = tmp_path / BINDINGS
    target.parent.mkdir(parents=True)
    baseline = json.loads((ROOT / BINDINGS).read_text())
    original_lanes = {row['lane']: row for row in baseline['lanes']}
    for control in controls:
        original_lanes[lane]['controls'][control]['status'] = 'UNVERIFIED'
    target.write_text(json.dumps(baseline))
    proof_path = ('runtime/campaigns_control/campaign_measured_outcome_latest.json'
                  if lane == 'campaigns' else 'runtime/opportunities_control/opportunities_final_controls_latest.json')
    proof = tmp_path / proof_path
    proof.parent.mkdir(parents=True, exist_ok=True)
    proof.write_text(json.dumps({'runtime_verified_controls': list(controls)}))
    source = (ROOT / 'scripts' / (name + '.py')).read_text()
    assert 'ROOT = Path("/srv/empire_os")' in source
    staged = tmp_path / (name + '.py')
    staged.write_text(source.replace('ROOT = Path("/srv/empire_os")', f'ROOT = Path({str(tmp_path)!r})', 1))
    result = subprocess.run([sys.executable, str(staged)], cwd=tmp_path,
                            env={**os.environ, 'PYTHONPATH': str(ROOT)},
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr + result.stdout
    updated = json.loads(target.read_text())
    row = next(item for item in updated['lanes'] if item['lane'] == lane)
    for control in controls:
        assert row['controls'][control]['status'] == 'VERIFIED_RUNTIME'
    assert not list(target.parent.glob('*.tmp*'))
