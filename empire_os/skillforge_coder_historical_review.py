"""Read-only, digest-pinned original Git revision replay for SkillForge.

The original source-release receipts, commit objects and source hashes were
verified before replay. A replay PASS is not production deployment, an
independent Department task, or authority to approve reusable skills.
"""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path
import json
import subprocess
from typing import Any

from empire_os.skillforge_coder_historical_release import RELEASES

RECEIPT = Path('config/skillforge_coder_original_revision_replay_20261021.json')
PINNED_SHA256 = 'c6af55d30365162ad1d90561dd3a5dcf6412a9a9ed88748001d89cee85289787'


def _hold(reason:str) -> dict[str,Any]:
    return {
        'schema_version':'empire.skillforge.original_revision_replay_review.v1',
        'status':reason,
        'historical_source_chains_verified':0,
        'original_git_revisions_with_replayed_tests':0,
        'historical_commits_on_current_branch':0,
        'production_deployment_verified':False,
        'independent_department_completion_attributed':False,
        'independent_implementation_outcome_verified':False,
        'automatic_skill_approval':False,
        'execution_authority':'none',
    }


def read_pinned_original_revision_replay(repo:Path)->dict[str,Any]:
    repo=Path(repo).resolve()
    file=repo/RECEIPT
    if not file.exists() and not file.is_symlink():
        return _hold('ORIGINAL_REVISION_REPLAY_NOT_INSTALLED')
    try:
        if (file.is_symlink() or file.parent.is_symlink()
            or not file.is_file() or not 0<file.stat().st_size<20000):
            raise ValueError('unsafe replay file')
        raw=file.read_bytes()
        if sha256(raw).hexdigest()!=PINNED_SHA256:
            raise ValueError('tampered replay bytes')
        report=json.loads(raw)
        exact={
            'schema_version':'empire.skillforge.original_coder_revision_test_replay.v1',
            'mode':'EXACT_HISTORICAL_GIT_REVISION_FIXED_TEST_ONLY',
            'status':'TWO_ORIGINAL_REVISION_TESTS_REEXECUTED_PASS',
            'original_releases_checked':2,
            'original_revisions_with_test_pass':2,
            'historical_commits_on_current_server_branch':0,
            'historical_department_work_completion_link_verified':False,
            'independent_agent_code_outcomes_verified':0,
            'production_deployment_verified':False,
            'skillforge_auto_approval':False,
            'execution_authority':'none',
        }
        if not isinstance(report,dict) or any(report.get(k)!=v for k,v in exact.items()):
            raise ValueError('forged replay authority or counts')
        rows=report.get('releases')
        if (not isinstance(rows,list) or len(rows)!=2
            or {r.get('release') for r in rows if isinstance(r,dict)}
                 !={spec['name'] for spec in RELEASES}):
            raise ValueError('missing original fixed releases')
        for spec in RELEASES:
            r=next(r for r in rows if r['release']==spec['name'])
            expected={
                'release':spec['name'],
                'git_commit_sha256':sha256(spec['source_commit'].encode()).hexdigest(),
                'original_receipt_sha256':spec['sha256'],
                'exact_original_revision_test_file':spec['test'],
                'replay_status':'ORIGINAL_REVISION_TESTS_REEXECUTED_PASS',
                'test_process_exit_code':0,
                'independent_release_owner_attestation':False,
                'reproduced_test_result_is_not_deployment_proof':True,
                'same_original_revision_after':True,
                'test_source_unchanged_after':True,
                'worktree_clean_after':True,
            }
            if (set(r)!=set(expected)|{'original_test_blob_sha256'}
                or any(r.get(k)!=v for k,v in expected.items())):
                raise ValueError('original replay result mismatch')
            proc=subprocess.run(
                ['git','show',spec['source_commit']+':'+spec['test']],
                cwd=repo,capture_output=True,timeout=12,check=False)
            if (proc.returncode!=0
                or sha256(proc.stdout).hexdigest()!=r['original_test_blob_sha256']):
                raise ValueError('historical test source blob not reproduced')
        return {
            **_hold('PINNED_TWO_ORIGINAL_REVISION_TEST_REPLAYS_REVIEW_ONLY'),
            'historical_source_chains_verified':2,
            'original_git_revisions_with_replayed_tests':2,
            'source_evidence_receipt_sha256':PINNED_SHA256,
            'missing_owner_evidence_requirements':(
                'Source owner attribution to canonical Department work, '
                'independent changed-code outcome verification, and '
                'explicit trust-registry digest approval'),
        }
    except (OSError,ValueError,UnicodeError,TypeError,subprocess.SubprocessError):
        return _hold('ORIGINAL_REVISION_REPLAY_TAMPER_OR_INTEGRITY_HOLD')
