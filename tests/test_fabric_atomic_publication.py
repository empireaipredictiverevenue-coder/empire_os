"""Fabric output publication must never use a shared fixed temp name."""
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_fabric_atomic_publication(tmp_path):
    source = (ROOT / 'scripts/apply_runtime_control_bindings.py').read_text()
    tree = ast.parse(source)
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'atomic_write')
    scope = ast.Module(body=[function], type_ignores=[])
    import os
    import tempfile
    namespace = {'json': json, 'Path': Path, 'os': os, 'tempfile': tempfile}
    exec(compile(scope, '<atomic-write>', 'exec'), namespace)
    target = tmp_path / 'detection_fabric_latest.json'
    target.write_text('old')
    namespace['atomic_write'](target, {'mode': 'OBSERVE', 'verified': 3})
    assert json.loads(target.read_text()) == {'mode': 'OBSERVE', 'verified': 3}
    assert not list(tmp_path.glob('*.tmp'))
    assert not (tmp_path / 'detection_fabric_latest.tmp').exists()
