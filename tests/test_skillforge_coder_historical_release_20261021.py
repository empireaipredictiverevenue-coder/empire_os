"""Original first-party Coder releases: Git source proof, not skill approval."""
from hashlib import sha256
from pathlib import Path
import json
import shutil
import pytest

from empire_os.skillforge_coder_historical_release import (
    RELEASES, audit_original_coder_release_sources,
    _original_release_evidence,
)
ROOT=Path(__file__).resolve().parents[1]
ORIGINAL=Path('/srv/empire_os')


def fixture_receipts(root:Path):
    for item in RELEASES:
        file=root/item['path']
        file.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ORIGINAL/item['path'],file)
    return root


def test_two_genuine_committed_source_chains_are_verified_without_approval():
    data=audit_original_coder_release_sources(ORIGINAL,ROOT)
    assert data['status']=='TWO_HISTORICAL_RELEASE_SOURCE_CHAINS_VERIFIED'
    assert data['historical_receipts_checked']==2
    assert data['git_source_chains_verified']==2
    assert data['historical_release_commits_on_current_head_ancestry']==0
    assert data['independent_department_completions_proven']==0
    assert data['independently_authenticated_production_deployments']==0
    assert data['independently_verified_skill_outcomes']==0
    assert data['skillforge_auto_approval'] is False
    assert all(r['commit_parent_source_bytes_verified'] is True
               and r['commit_changed_file_hashes_verified'] is True
               and r['exact_historical_revision_test_replayed'] is False
               and r['independent_department_completion_attributed'] is False
               for r in data['release_provenance'])


def test_copied_original_receipt_digests_are_identical(tmp_path):
    cloned=fixture_receipts(tmp_path)
    data=audit_original_coder_release_sources(cloned,ROOT)
    assert data['git_source_chains_verified']==2


def test_missing_original_receipt_is_a_hold(tmp_path):
    cloned=fixture_receipts(tmp_path)
    (cloned/RELEASES[0]['path']).unlink()
    data=audit_original_coder_release_sources(cloned,ROOT)
    assert data['git_source_chains_verified']==1
    assert data['status']=='ORIGINAL_RELEASE_SOURCE_CHAIN_HOLD'


def test_symlinked_original_receipt_is_rejected(tmp_path):
    cloned=fixture_receipts(tmp_path)
    path=cloned/RELEASES[0]['path']
    path.unlink()
    path.symlink_to(ORIGINAL/RELEASES[0]['path'])
    data=audit_original_coder_release_sources(cloned,ROOT)
    assert data['git_source_chains_verified']==1
    assert data['skillforge_auto_approval'] is False


@pytest.mark.parametrize('mutation',[
    lambda r:r.update(source_commit='f'*40),
    lambda r:r.update(prior_head='f'*40),
    lambda r:r['sha256'].update({next(iter(r['sha256'])):'f'*64}),
    lambda r:r['old_hex'].update({next(iter(r['old_hex'])):'01'}),
    lambda r:r.update(paths=['../../outside.py']),
])
def test_modified_original_receipt_fails_even_if_new_digest_is_pinned_in_test_only(
    tmp_path,mutation,
):
    item=RELEASES[1]
    original=json.loads((ORIGINAL/item['path']).read_text())
    mutation(original)
    path=tmp_path/item['path']
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(original))
    changed_item={
        **item,'sha256':sha256(path.read_bytes()).hexdigest(),
    }
    data=_original_release_evidence(tmp_path,ROOT,changed_item)
    assert data['status']=='ORIGINAL_GIT_RELEASE_SOURCE_CHAIN_HOLD'
    assert data['commit_changed_file_hashes_verified'] is False
    assert data['skill_promotion_authorized'] is False


def test_unmodified_original_does_not_become_current_production_commit():
    data=audit_original_coder_release_sources(ORIGINAL,ROOT)
    assert all(not r['git_commit_on_current_head_ancestry']
               for r in data['release_provenance'])
    assert data['independently_authenticated_production_deployments']==0
