"""Bounded original-revision test replay cannot become automatic approval."""
from pathlib import Path
from types import SimpleNamespace
import pytest
from empire_os.skillforge_coder_historical_release import RELEASES
from empire_os.skillforge_coder_historical_replay import replay_exact_original_releases

ROOT=Path(__file__).resolve().parents[1]
ORIGINAL=Path('/srv/empire_os')
WORKTREES=(
    Path('/home/ubuntu/empire_worktrees/skillforge_original_deadline_20261021'),
    Path('/home/ubuntu/empire_worktrees/skillforge_original_provider_20261021'),
)


def test_original_worktrees_pinned_commits_and_fixed_tests():
    seen=[]
    def fake_run(args,**kwargs):
        assert args[-1] in [str(worktrees/record['test'])
                            for worktrees,record in zip(WORKTREES,RELEASES)]
        assert args[0].endswith('python')
        assert kwargs['timeout']<=45
        assert kwargs['env']['PYTEST_DISABLE_PLUGIN_AUTOLOAD']=='1'
        seen.append(args[-1])
        return SimpleNamespace(returncode=0)
    report=replay_exact_original_releases(
        ORIGINAL,ROOT,WORKTREES,execute=fake_run)
    assert report['original_revisions_with_test_pass']==2
    assert len(seen)==2
    assert report['historical_department_work_completion_link_verified'] is False
    assert report['production_deployment_verified'] is False
    assert report['skillforge_auto_approval'] is False


def test_historical_pytest_failure_does_not_become_skill_success():
    def nonpassing(*args,**kwargs):
        return SimpleNamespace(returncode=2)
    report=replay_exact_original_releases(
        ORIGINAL,ROOT,WORKTREES,execute=nonpassing)
    assert report['status']=='ORIGINAL_TEST_REPLAY_HOLD'
    assert report['original_revisions_with_test_pass']==0
    assert report['skillforge_auto_approval'] is False


def test_historical_worktrees_cannot_be_current_production_repo():
    with pytest.raises(ValueError):
        replay_exact_original_releases(
            ORIGINAL,ROOT,(ORIGINAL,WORKTREES[1]),
            execute=lambda *a,**kw:SimpleNamespace(returncode=0))


def test_swapped_historical_worktrees_fail_revision_check():
    with pytest.raises(ValueError):
        replay_exact_original_releases(
            ORIGINAL,ROOT,(WORKTREES[1],WORKTREES[0]),
            execute=lambda *a,**kw:SimpleNamespace(returncode=0))


def test_unclean_original_revision_rejected(monkeypatch):
    import empire_os.skillforge_coder_historical_replay as module
    previous=module._git
    def unclean(repo,*args):
        if args and args[0]=='status':
            return ' M suspect_test.py'
        return previous(repo,*args)
    monkeypatch.setattr(module,'_git',unclean)
    with pytest.raises(ValueError,match='clean'):
        replay_exact_original_releases(
            ORIGINAL,ROOT,WORKTREES,
            execute=lambda *a,**kw:SimpleNamespace(returncode=0))


def test_timeout_fails_both_historical_replays_without_inventing_a_pass():
    import subprocess
    def timeout(*args,**kwargs):
        raise subprocess.TimeoutExpired(args[0],kwargs['timeout'])
    report=replay_exact_original_releases(
        ORIGINAL,ROOT,WORKTREES,execute=timeout)
    assert report['status']=='ORIGINAL_TEST_REPLAY_HOLD'
    assert report['original_revisions_with_test_pass']==0
    assert all(x['test_process_exit_code'] is None for x in report['releases'])
