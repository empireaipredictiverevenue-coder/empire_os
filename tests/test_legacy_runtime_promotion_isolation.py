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
