import json
from pathlib import Path

from empire_os.model_registry import ModelRegistry


def _registry(tmp_path: Path, health):
    registry_path=tmp_path/'registry.json'
    health_path=tmp_path/'health.json'
    registry_path.write_text(json.dumps({'models':[
        {'model_id':'bad','provider':'gemini','model':'bad-model','capabilities':['general'],'quality':{'default':0.95},'enabled':True,'available':True},
        {'model_id':'good','provider':'local','model':'good-model','capabilities':['general'],'quality':{'default':0.50},'enabled':True,'available':True},
    ]}))
    health_path.write_text(json.dumps({'schema_version':'model_health.v1','models':health}))
    return ModelRegistry(str(registry_path),health_path=str(health_path))


def test_degraded_route_with_enough_samples_is_demoted(tmp_path):
    r=_registry(tmp_path,{'gemini:bad-model':{'status':'degraded','samples':10,'successes':0,'failures':10,'success_rate':0.0,'avg_latency_ms':100}})
    bad=r.get('bad')
    assert bad is not None
    assert bad.available is False
    assert bad.health=='degraded'
    assert bad.metadata['runtime_health_evidence']['failures']==10
    ids={m.model_id for m in r.candidates(task='general')}
    assert 'bad' not in ids
    assert 'good' in ids


def test_degraded_route_below_sample_floor_is_not_demoted(tmp_path):
    r=_registry(tmp_path,{'gemini:bad-model':{'status':'degraded','samples':4,'successes':0,'failures':4}})
    assert r.get('bad').available is True


def test_warning_and_healthy_routes_remain_available(tmp_path):
    for status in ('warning','healthy'):
        r=_registry(tmp_path,{'gemini:bad-model':{'status':status,'samples':20,'successes':19,'failures':1}})
        assert r.get('bad').available is True
        assert r.get('bad').health==status


def test_missing_health_preserves_configured_availability(tmp_path):
    r=_registry(tmp_path,{})
    assert r.get('bad').available is True
    assert r.get('bad').health=='unknown'
