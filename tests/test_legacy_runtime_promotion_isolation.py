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


def test_campaign_final_success_on_disposable_full_canonical(tmp_path):
    import json
    target = tmp_path / BINDINGS
    target.parent.mkdir(parents=True)
    data = json.loads((ROOT / BINDINGS).read_text())
    campaign = next(row for row in data['lanes'] if row['lane'] == 'campaigns')
    for row in campaign['controls'].values():
        row['status'] = 'VERIFIED_RUNTIME'
    target.write_text(json.dumps(data))
    proof = tmp_path / 'runtime/campaigns_control/campaign_output_outcome_latest.json'
    proof.parent.mkdir(parents=True)
    proof.write_text(json.dumps({'runtime_verified_controls': ['output_quality', 'outcome_linkage']}))
    source = (ROOT / 'scripts/promote_campaign_final_bindings.py').read_text()
    staged = tmp_path / 'promote_campaign_final_bindings.py'
    staged.write_text(source.replace('ROOT = Path("/srv/empire_os")', f'ROOT = Path({str(tmp_path)!r})', 1))
    result = subprocess.run([sys.executable, str(staged)], cwd=tmp_path,
                            env={**os.environ, 'PYTHONPATH': str(ROOT)},
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr + result.stdout
    assert 'CANONICAL_VERIFIED_COUNT:' in result.stdout
    assert len([row for row in json.loads(target.read_text())['lanes'] if row['lane'] == 'campaigns'][0]['controls']) == 11


def test_reconciler_rejects_materialized_founder_authority(tmp_path):
    import json
    target = tmp_path / BINDINGS
    target.parent.mkdir(parents=True)
    data = json.loads((ROOT / BINDINGS).read_text())
    target.write_text(json.dumps(data))
    fabric = {'lanes': [{'lane': 'consent_suppression', 'runtime_verified_control_count': 11,
                         'runtime_unverified_controls': []}]}
    f = tmp_path / 'runtime/control_plane/detection_fabric_latest.json'
    f.write_text(json.dumps(fabric))
    source = (ROOT / 'scripts/reconcile_materialized_runtime_bindings.py').read_text()
    staged = tmp_path / 'reconcile_materialized_runtime_bindings.py'
    staged.write_text(source.replace('ROOT = Path("/srv/empire_os")', f'ROOT = Path({str(tmp_path)!r})', 1))
    before = target.read_bytes()
    result = subprocess.run([sys.executable, str(staged)], cwd=tmp_path,
                            env={**os.environ, 'PYTHONPATH': str(ROOT)},
                            capture_output=True, text=True, timeout=15)
    assert result.returncode != 0
    assert target.read_bytes() == before


def test_reconciler_success_with_consistent_disposable_fabric(tmp_path):
    """Reconcile one lane with exact matching materialized and canonical truth."""
    import json
    target = tmp_path / BINDINGS
    target.parent.mkdir(parents=True)
    baseline = json.loads((ROOT / BINDINGS).read_text())
    lane = next(row for row in baseline['lanes'] if row['lane'] == 'leads')
    verified = {key for key, value in lane['controls'].items() if value.get('status') == 'VERIFIED_RUNTIME'}
    remaining = sorted(set(lane['controls']) - verified)
    target.write_text(json.dumps(baseline))
    fabric = {'lanes': [{'lane': 'leads', 'runtime_verified_control_count': len(verified),
                         'runtime_unverified_controls': remaining}]}
    f = tmp_path / 'runtime/control_plane/detection_fabric_latest.json'
    f.write_text(json.dumps(fabric))
    source = (ROOT / 'scripts/reconcile_materialized_runtime_bindings.py').read_text()
    assert 'ROOT = Path("/srv/empire_os")' in source
    staged = tmp_path / 'reconcile_materialized_runtime_bindings.py'
    staged.write_text(source.replace('ROOT = Path("/srv/empire_os")', f'ROOT = Path({str(tmp_path)!r})', 1))
    result = subprocess.run([sys.executable, str(staged)], cwd=tmp_path,
                            env={**os.environ, 'PYTHONPATH': str(ROOT)},
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr + result.stdout
    updated = json.loads(target.read_text())
    assert updated['materialized_runtime_reconciled_at']
    updated_lane = next(row for row in updated['lanes'] if row['lane'] == 'leads')
    assert {key for key, value in updated_lane['controls'].items() if value.get('status') == 'VERIFIED_RUNTIME'} == verified
    assert not list(target.parent.glob('*.tmp*'))
