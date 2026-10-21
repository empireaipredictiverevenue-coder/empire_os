"""Distinguish source-attested Git changes from intended paths and pytest flags."""
from pathlib import Path
import json
import subprocess
import pytest
from empire_os.skillforge_coder_patch_provenance import (
    audit_selected_coder_patch_provenance,check_original_coder_commit,
)


def git(root,*args):
    result=subprocess.run(['git',*args],cwd=root,check=False,
                          capture_output=True,text=True)
    assert result.returncode==0,(args,result.stderr)
    return result.stdout.strip()


def source_repo(tmp_path):
    root=tmp_path/'repo'
    root.mkdir()
    git(root,'init','-q')
    (root/'empire_os').mkdir()
    (root/'tests').mkdir()
    files=('empire_os/safe_component.py','tests/test_safe_component.py')
    for filename in files:
        file=root/filename;file.write_text('x = 1\n')
    git(root,'add',*files)
    git(root,'-c','user.email=local@invalid.example',
        '-c','user.name=Test Fixture','commit','-qm','baseline')
    (root/files[0]).write_text('x = 2\n')
    (root/files[1]).write_text('def test_safe(): assert True\n')
    git(root,'add',*files)
    git(root,'-c','user.email=local@invalid.example',
        '-c','user.name=Test Fixture','commit','-qm','candidate')
    return root,git(root,'rev-parse','HEAD'),files


def original_job(commit,changed):
    tests=['tests/test_safe_component.py']
    return {
        'kind':'VERIFY','status':'COMPLETED',
        'payload':{
            'tests':tests,
            'changed_files':list(changed),
            'source_plan_job_id':'coder_job_'+'a'*32,
        },
        'result':{
            'tests':tests,
            'implementation_commit_sha':commit,
            'verification':{
                'verdict':'PASS',
                'checks':[
                    {'name':'pytest','passed':True,'returncode':0,'tests':tests},
                    {'name':'git_diff_check','passed':True,'returncode':0},
                ],
            },
        },
    }


def test_real_matching_commit_counts_as_path_link_not_execution(tmp_path):
    repo,head,files=source_repo(tmp_path)
    report=check_original_coder_commit(repo,original_job(head,files))
    assert report['status']=='ORIGINAL_GIT_COMMIT_PATHS_MATCHED_REVIEW_ONLY'
    assert report['explicit_original_implementation_commit_present'] is True
    assert report['git_commit_path_set_confirmed'] is True
    assert report['changed_python_file_count']==2
    assert report['independently_verified_implementation'] is False
    assert report['source_deployment_verified'] is False
    assert report['automatic_skill_promotion'] is False


def test_missing_original_implementation_commit_is_not_inferred(tmp_path):
    repo,head,files=source_repo(tmp_path)
    original=original_job(head,files)
    del original['result']['implementation_commit_sha']
    report=check_original_coder_commit(repo,original)
    assert report['status']=='MISSING_EXPLICIT_IMPLEMENTATION_COMMIT'
    assert report['git_commit_path_set_confirmed'] is False


@pytest.mark.parametrize('claim',[
    'no-commit', 'f'*40, '../shell', 42, True,
])
def test_untrusted_commit_claim_cannot_be_path_evidence(tmp_path,claim):
    repo,head,files=source_repo(tmp_path)
    report=check_original_coder_commit(repo,original_job(claim,files))
    assert report['git_commit_path_set_confirmed'] is False
    assert report['automatic_skill_promotion'] is False


def test_unrelated_commit_does_not_prove_requested_patch(tmp_path):
    repo,head,files=source_repo(tmp_path)
    report=check_original_coder_commit(repo,original_job(head,[files[0]]))
    assert report['status']=='CLAIMED_PATHS_NOT_EXACT_GIT_DIFF'
    assert report['git_commit_path_set_confirmed'] is False


@pytest.mark.parametrize('path',[
    '../../outside.py','/etc/passwd','empire_os/../../escape.py',
    'tests/../empire_os/safe_component.py','docs/change.md',
    'empire_os/safe_component.py\x00other.py',
])
def test_unsafe_changed_paths_rejected(tmp_path,path):
    repo,head,files=source_repo(tmp_path)
    packet=original_job(head,[files[0],path])
    result=check_original_coder_commit(repo,packet)
    assert result['status']=='UNSAFE_OR_NONCODE_CHANGED_PATHS'
    assert result['git_commit_path_set_confirmed'] is False


def test_fake_test_verdict_does_not_validate_code_commit(tmp_path):
    repo,head,files=source_repo(tmp_path)
    packet=original_job(head,files)
    packet['result']['verification']['checks'][0]['returncode']=1
    result=check_original_coder_commit(repo,packet)
    assert result['status']=='INELIGIBLE_OR_UNSUPPORTED_VERIFY_JOB'
    assert result['automatic_skill_promotion'] is False


def test_root_commit_does_not_count_as_attributed_patch(tmp_path):
    repo,head,files=source_repo(tmp_path)
    root=git(repo,'rev-list','--max-parents=0','HEAD')
    record=check_original_coder_commit(repo,original_job(root,files))
    assert record['status']=='MERGE_OR_ROOT_COMMIT_REQUIRES_OWNER_REVIEW'


def test_live_original_receipts_have_no_implementation_commit_link():
    result=audit_selected_coder_patch_provenance(
        Path('/srv/empire_os'),Path(__file__).resolve().parents[1])
    assert result['selected_original_job_count']==2
    assert result['missing_explicit_implementation_commit_count']==2
    assert result['historical_source_commit_path_matches']==0
    assert result['independent_code_implementations_verified']==0
    assert result['skillforge_auto_approval'] is False
    assert all(entry['status']=='MISSING_EXPLICIT_IMPLEMENTATION_COMMIT'
               for entry in result['individual_original_receipts'])
