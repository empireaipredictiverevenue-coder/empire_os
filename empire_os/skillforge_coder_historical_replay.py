"""Re-run fixed tests at two exact original Coder release commits.

The chosen Git worktrees must already exist, be detached and clean. Original
JSON never provides executable commands, test paths or target branches.
"""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path
import os
import subprocess
import sys
from typing import Any,Callable

from empire_os.skillforge_coder_historical_release import (
    RELEASES,audit_original_coder_release_sources,
)
TIMEOUT=45


def _git(root:Path,*args:str)->str:
    proc=subprocess.run(["git",*args],cwd=root,capture_output=True,
                        text=True,timeout=12,check=False)
    if proc.returncode!=0:
        raise ValueError("isolated Git worktree check failed")
    return proc.stdout.strip()


def replay_exact_original_releases(
    original_root:Path, repo:Path, worktrees:tuple[Path,Path], *,
    execute:Callable[...,Any]=subprocess.run,
)->dict[str,Any]:
    original_root=Path(original_root).resolve()
    repo=Path(repo).resolve()
    if len(worktrees)!=len(RELEASES):
        raise ValueError("original release replay needs two explicit worktrees")
    evidence=audit_original_coder_release_sources(original_root,repo)
    if evidence['status']!='TWO_HISTORICAL_RELEASE_SOURCE_CHAINS_VERIFIED':
        raise ValueError("original release/source chain not verified")
    rows=[]
    for spec,given,proof in zip(RELEASES,worktrees,evidence['release_provenance']):
        worktree=Path(given).resolve()
        if (worktree in (original_root,repo) or not (worktree/'.git').exists()
            or _git(worktree,'branch','--show-current')
            or _git(worktree,'rev-parse','HEAD')!=spec['source_commit']
            or _git(worktree,'status','--porcelain','--untracked-files=normal')):
            raise ValueError("historical revision worktree must be detached and clean")
        test=worktree/spec['test']
        if (test.is_symlink() or (worktree/'tests').is_symlink()
            or not test.is_file()
            or not 0<test.stat().st_size<=256000):
            raise ValueError("historical test file missing or unsafe")
        original_hash=sha256(test.read_bytes()).hexdigest()
        if original_hash!=proof['historical_test_blob_sha256']:
            raise ValueError("original test source differs from exact Git revision")
        env=os.environ.copy()
        env['PYTHONDONTWRITEBYTECODE']='1'
        env['PYTHONPATH']=str(worktree)
        env['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1'
        env.pop('PYTEST_ADDOPTS',None)
        command=[
            sys.executable,'-B','-m','pytest','-q','-p','no:cacheprovider',
            '--rootdir',str(worktree),str(test),
        ]
        status='REPLAY_HOLD'
        exitcode=None
        try:
            result=execute(command,cwd=worktree,env=env,
                           capture_output=True,text=True,timeout=TIMEOUT,check=False)
            if type(result.returncode) is int:
                exitcode=result.returncode
        except (OSError,subprocess.TimeoutExpired):
            exitcode=None
        clean=not bool(_git(worktree,'status','--porcelain','--untracked-files=normal'))
        same_commit=_git(worktree,'rev-parse','HEAD')==spec['source_commit']
        same_test=sha256(test.read_bytes()).hexdigest()==original_hash
        if exitcode==0 and clean and same_commit and same_test:
            status='ORIGINAL_REVISION_TESTS_REEXECUTED_PASS'
        rows.append({
            'release':spec['name'],
            'git_commit_sha256':sha256(spec['source_commit'].encode()).hexdigest(),
            'original_receipt_sha256':spec['sha256'],
            'exact_original_revision_test_file':spec['test'],
            'original_test_blob_sha256':original_hash,
            'test_process_exit_code':exitcode,
            'replay_status':status,
            'worktree_clean_after':clean,
            'same_original_revision_after':same_commit,
            'test_source_unchanged_after':same_test,
            'independent_release_owner_attestation':False,
            'reproduced_test_result_is_not_deployment_proof':True,
        })
    return {
        'schema_version':'empire.skillforge.original_coder_revision_test_replay.v1',
        'mode':'EXACT_HISTORICAL_GIT_REVISION_FIXED_TEST_ONLY',
        'status':('TWO_ORIGINAL_REVISION_TESTS_REEXECUTED_PASS'
                  if all(x['replay_status']=='ORIGINAL_REVISION_TESTS_REEXECUTED_PASS'
                         for x in rows) else 'ORIGINAL_TEST_REPLAY_HOLD'),
        'original_releases_checked':len(rows),
        'original_revisions_with_test_pass':sum(
            x['replay_status']=='ORIGINAL_REVISION_TESTS_REEXECUTED_PASS'
            for x in rows),
        'releases':rows,
        'historical_commits_on_current_server_branch':(
            evidence['historical_release_commits_on_current_head_ancestry']),
        'production_deployment_verified':False,
        'historical_department_work_completion_link_verified':False,
        'independent_agent_code_outcomes_verified':0,
        'skillforge_auto_approval':False,
        'execution_authority':'none',
    }
