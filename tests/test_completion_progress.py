import json, subprocess
from pathlib import Path
from empire_os.completion_progress import checklist_counts, reconcile_completion_progress

def test_checklist_counts_truth(tmp_path: Path):
    p=tmp_path/'check.md'; p.write_text('- [x] a\n- [X] b\n- [ ] c\n')
    assert checklist_counts(p)=={'master_checklist_done':2,'master_checklist_pending':1,'master_checklist_total':3}

def test_reconcile_uses_live_git_checklist_and_leases(tmp_path: Path):
    repo=tmp_path/'repo'; repo.mkdir(); subprocess.run(['git','init','-q','-b','main',str(repo)],check=True)
    subprocess.run(['git','-C',str(repo),'config','user.email','test@example.invalid'],check=True); subprocess.run(['git','-C',str(repo),'config','user.name','Test'],check=True)
    (repo/'x').write_text('x'); subprocess.run(['git','-C',str(repo),'add','x'],check=True); subprocess.run(['git','-C',str(repo),'commit','-qm','x'],check=True)
    progress=tmp_path/'progress.json'; progress.write_text(json.dumps({'head':'stale','active_atomic_builders':{'old':'running'},'diagram_evidence':{}}))
    checklist=tmp_path/'check.md'; checklist.write_text('- [x] done\n- [ ] todo\n'); leases=tmp_path/'leases.json'; leases.write_text('[]')
    out=reconcile_completion_progress(repo=repo,progress_path=progress,checklist_path=checklist,leases_path=leases)
    assert out['branch']=='main' and out['head']!='stale' and out['active_atomic_builders']=={}
    assert out['diagram_evidence']['master_checklist_done']==1 and json.loads(progress.read_text())['diagram_evidence']['master_checklist_total']==2
    assert out['master_checklist']=={'done':1,'pending':1,'total':2}
