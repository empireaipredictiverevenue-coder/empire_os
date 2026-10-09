from __future__ import annotations
import importlib.util
from pathlib import Path
import json
import sys
from test_factory_hybrid_review_v1 import fixture

SCRIPT=Path(__file__).resolve().parents[1]/'scripts'/'check_factory_hybrid_review_v1.py'
spec=importlib.util.spec_from_file_location('p4cli',SCRIPT)
cli=importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


def test_read_only_diagnostic_for_valid_held_work(tmp_path,monkeypatch,capsys):
    path=tmp_path/'runtime'/'departments'/'work'/'blocked'
    path.mkdir(parents=True)
    item=fixture()['work_item']
    (path/'work-42.json').write_text(json.dumps(item))
    monkeypatch.setattr(sys,'argv',['review','--repo-root',str(tmp_path),'--work-id','work-42'])
    assert cli.main()==0
    result=json.loads(capsys.readouterr().out)
    assert result['status']=='AWAITING_AUTHENTICATED_REVIEW'
    assert result['queue_mutated'] is False
    assert result['department_work_done'] is False
    assert (path/'work-42.json').read_text()==json.dumps(item)


def test_missing_work_reported_blocked(tmp_path,monkeypatch,capsys):
    monkeypatch.setattr(sys,'argv',['review','--repo-root',str(tmp_path),'--work-id','work-42'])
    assert cli.main()==2
    assert 'work_identity_missing_or_ambiguous' in capsys.readouterr().out


def test_reject_invalid_work_id(tmp_path,monkeypatch):
    import pytest
    monkeypatch.setattr(sys,'argv',['review','--repo-root',str(tmp_path),'--work-id','../../root'])
    with pytest.raises(SystemExit):cli.main()


def test_reject_duplicate_held_records(tmp_path,monkeypatch,capsys):
    for name in ('blocked','review'):
        p=tmp_path/'runtime'/'departments'/'work'/name
        p.mkdir(parents=True)
        (p/'work-42.json').write_text(json.dumps(fixture()['work_item']))
    monkeypatch.setattr(sys,'argv',['review','--repo-root',str(tmp_path),'--work-id','work-42'])
    assert cli.main()==2
    assert 'ambiguous' in capsys.readouterr().out
