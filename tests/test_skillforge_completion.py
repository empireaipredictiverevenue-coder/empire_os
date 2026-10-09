"""Final SkillForge acceptance: real source checks and explicit external gates."""
from __future__ import annotations
import json
from pathlib import Path
import shutil

from empire_os.skillforge_completion import completion_report

ROOT=Path(__file__).resolve().parents[1]


def _safe_contract_repo(tmp_path):
    """Pure isolated clone of governed pack and authored holdout inputs."""
    library = tmp_path / 'empire_os/skills_library/skills'
    library.mkdir(parents=True)
    for source in (ROOT/'empire_os/skills_library/skills').glob('empire-*/SKILL.md'):
        dest=library/source.parent.name/'SKILL.md'
        dest.parent.mkdir(parents=True)
        shutil.copyfile(source, dest)
    config = tmp_path/'config/skill_trust_registry.json'
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps({'schema_version':'empire.skill_trust.v1','approved_skills':{}}))
    fixtures=tmp_path/'tests/fixtures/skillforge_domain'
    fixtures.mkdir(parents=True)
    for source in (ROOT/'tests/fixtures/skillforge_domain').glob('*.json'):
        shutil.copyfile(source,fixtures/source.name)
    return tmp_path


def test_close_engineering_without_claiming_approval(tmp_path):
    root=_safe_contract_repo(tmp_path)
    before=set(root.rglob('*'))
    report=completion_report(root)
    assert report['engineering_verified'] is True
    assert report['engineering_checks_total']==8
    assert report['engineering_checks_passed']==8
    assert report['skill_count']>=12
    assert report['approved_skill_count']==0
    assert report['verified_observation_count']==0
    assert report['pending_review_draft_count']==0
    assert len(report['domain_replays'])==2
    assert report['independent_quality_verified'] is False
    assert report['skill_promoted'] is False
    assert report['production_changes_performed'] is False
    assert all(not row['independently_verified'] for row in report['domain_replays'])
    assert set(root.rglob('*')) == before  # no write or side effect


def test_live_evidence_required_cannot_be_inferred_from_code(tmp_path):
    root=_safe_contract_repo(tmp_path)
    report=completion_report(root, require_runtime_observations=True)
    assert report['engineering_verified'] is False
    fail={row['name'] for row in report['engineering_checks'] if not row['passed']}
    assert {'canonical_learning_provenance','immutable_private_review_drafts'}<=fail


def test_corrupted_registry_digest_fails_closure(tmp_path):
    root=_safe_contract_repo(tmp_path)
    registry=root/'config/skill_trust_registry.json'
    registry.write_text(json.dumps({'schema_version':'empire.skill_trust.v1','approved_skills':{
        'empire-reply-triage':{'status':'approved','sha256':'0'*64},
    }}))
    report=completion_report(root)
    assert report['engineering_verified'] is False
    fail={row['name'] for row in report['engineering_checks'] if not row['passed']}
    assert 'all_registry_approvals_load_verified' in fail
    assert 'no_implicit_skill_approval' in fail


def test_third_party_entry_cannot_count_as_approved(tmp_path):
    root=_safe_contract_repo(tmp_path)
    registry=root/'config/skill_trust_registry.json'
    registry.write_text(json.dumps({'schema_version':'empire.skill_trust.v1','approved_skills':{
        'brand-guidelines':{'status':'approved','sha256':'0'*64},
    }}))
    report=completion_report(root)
    assert report['engineering_verified'] is False
    assert next(x for x in report['engineering_checks']
                if x['name']=='all_registry_approvals_load_verified')['passed'] is False


def test_missing_pack_never_passes_task_route(tmp_path):
    root=_safe_contract_repo(tmp_path)
    (root/'empire_os/skills_library/skills/empire-reply-triage/SKILL.md').unlink()
    report=completion_report(root)
    assert report['engineering_verified'] is False
    assert next(x for x in report['engineering_checks']
                if x['name']=='all_department_skill_routes_resolve')['passed'] is False


def test_bad_authored_holdout_fails_without_approved_skill(tmp_path):
    root=_safe_contract_repo(tmp_path)
    fixture=root/'tests/fixtures/skillforge_domain/predictive_cloud_v1.json'
    fixture.write_text('not a json fixture')
    report=completion_report(root)
    assert report['engineering_verified'] is False
    assert next(x for x in report['engineering_checks']
                if x['name']=='domain_evaluation_contracts')['passed'] is False
    assert report['approved_skill_count']==0


def test_corrupted_observation_blocks_closure(tmp_path):
    root=_safe_contract_repo(tmp_path)
    observed=root/'runtime/skillforge/observations'
    observed.mkdir(parents=True)
    (observed/'skill_observation_fake.json').write_text('{"approved":true}')
    report=completion_report(root)
    assert report['engineering_verified'] is False
    assert next(x for x in report['engineering_checks']
                if x['name']=='canonical_learning_provenance')['passed'] is False


def test_unapproved_review_draft_is_not_a_skill(tmp_path):
    root=_safe_contract_repo(tmp_path)
    proposals=root/'runtime/skillforge/proposals'
    proposals.mkdir(parents=True)
    # An arbitrary or altered draft is rejected, even if its name appears valid.
    draft=proposals/'skill_proposal_fake'
    draft.mkdir()
    (draft/'manifest.json').write_text(json.dumps({'status':'DRAFT_REVIEW_REQUIRED','approved':False}))
    (draft/'SKILL.md').write_text('# Raw draft')
    report=completion_report(root)
    assert report['engineering_verified'] is False
    assert next(x for x in report['engineering_checks']
                if x['name']=='immutable_private_review_drafts')['passed'] is False


def test_gauntlet_list_cannot_include_operations_or_production_paths():
    from scripts.verify_skillforge_completion import GAUNTLET_TESTS
    assert GAUNTLET_TESTS
    assert all(str(x).startswith('tests/') for x in GAUNTLET_TESTS)
    assert len(GAUNTLET_TESTS)==len(set(GAUNTLET_TESTS))
    assert all((ROOT/path).exists() for path in GAUNTLET_TESTS)


def test_gauntlet_missing_file_fails_closed_without_running_commands(tmp_path):
    from scripts.verify_skillforge_completion import run_gauntlet
    result=run_gauntlet(tmp_path)
    assert result['passed'] is False
    assert result['reason']=='missing_test_contract'
    assert result['execution_authority']=='none'
