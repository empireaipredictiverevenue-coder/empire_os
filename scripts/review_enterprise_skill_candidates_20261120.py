"""Read-only portfolio skill review using the existing SkillForge trust/loading APIs.

In-memory approvals are intentionally confined to this process, never persisted.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import subprocess

from empire_os.skill_exchange import COMPONENT_TASKS, PORTFOLIO_TASK_SKILLS, recommend_work_item_skills
from empire_os.skill_trust import read_trust_registry, load_work_item_skill_context, MAX_AGENT_SKILL_BYTES
from empire_os.skillforge_evaluation import evaluate_skill
from empire_os.skill_review import review_local_skill
from empire_os.skillforge_promotion import promotion_preflight

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / 'empire_os/skills_library/skills'
TRUST = ROOT / 'config/skill_trust_registry.json'
DISPATCH = ROOT / 'runtime/astra/department_dispatch_latest.json'
LANES = {
    'buyer_relationship_research': 'sales_revenue',
    'knowledge_factory_document_review': 'market_intelligence',
    'data_brokerage_scientific_diligence': 'rd_innovation',
    'finance_source_document_review': 'finance_capital',
    'empire_product_ui_review': 'engineering',
    'media_os_editorial_review': 'marketing_growth',
    'commerceos_catalogue_fulfilment_review': 'product',
    'skillforge_quality_review': 'rd_innovation',
}


def licence_status(directory: Path, body: str) -> str:
    if 'license: Internal EmpireOS authored instructions' in body[:600]:
        return 'empire_internal_restricted_redistribution'
    p = directory / 'LICENSE.txt'
    if p.is_file():
        licence = p.read_text(encoding='utf-8')[:1100].lower()
        if 'apache license' in licence and 'version 2.0' in licence:
            return 'apache_2_0_documented'
        if 'governed by your agreement with' in licence and 'anthropic' in licence:
            return 'anthropic_service_terms_requires_legal_review'
        return 'license_file_requires_manual_review'
    return 'licence_undocumented_hold'


def git_file_state(path: Path) -> str:
    relative = str(path.relative_to(ROOT))
    p = subprocess.run(['git', 'status', '--porcelain=v1', '--', relative],
                       cwd=ROOT, capture_output=True, text=True, check=True)
    if not p.stdout.strip():
        return 'tracked_clean'
    if p.stdout.lstrip().startswith('??'):
        return 'untracked'
    return 'worktree_modified'



# Real first-party work provides reviewer source cases, never independent gold labels.
# Direct-component scopes are preferred; department-only scopes are flagged proxy.
EVIDENCE_SCOPES = {
    'empire-lead-research': ('component', 'buyer_owner_evidence_review'),
    'empire-identity-resolution': ('component', 'identity_enrichment'),
    'empire-evidence-verification': ('component', 'source_intelligence_review'),
    'empire-revenue-reconciliation': ('department', 'finance_capital'),
    'empire-seo-intelligence': ('component', 'seo_action_lifecycle'),
    'empire-product-catalog-verification': ('component', 'commercial_product_catalog'),
    'empire-fulfilment-verification': ('department', 'operations_fulfilment'),
    'empire-skill-authoring': ('component', 'agent_tool_execution_plane'),
}



def _request_shape_sha256(record: dict) -> str:
    """Hash substantive workflow inputs, excluding work ID and outcome state."""
    fields = ('target_component', 'action', 'intelligence_request',
              'memory_query', 'success_condition', 'authority')
    stable = [record.get(name) for name in fields]
    return sha256(json.dumps(stable, sort_keys=True, separators=(',', ':'),
                             ensure_ascii=True, default=str).encode()).hexdigest()


def real_evidence_review_inventory(repo_root: Path = ROOT) -> list[dict]:
    """Select real source records with hashes; do not invent labels or skill outcomes."""
    evidence_by_name = {name: {'done': [], 'blocked': [], 'failed': []} for name in EVIDENCE_SCOPES}
    for work_status in ('done', 'blocked', 'failed'):
        directory = repo_root / 'runtime/departments/work' / work_status
        if directory.is_symlink() or not directory.is_dir():
            continue
        for path in directory.glob('dept_work_*.json'):
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 256_000:
                continue
            raw = path.read_bytes()
            try:
                record = json.loads(raw)
            except (UnicodeError, ValueError):
                continue
            if not isinstance(record, dict) or record.get('id') != path.stem:
                continue
            if record.get('status', '').lower() != work_status:
                continue
            for name, (scope_type, scope_value) in EVIDENCE_SCOPES.items():
                matched = (record.get('target_component') == scope_value if scope_type == 'component'
                           else scope_value in record.get('department_keys', []))
                if not matched:
                    continue
                evidence_by_name[name][work_status].append({
                    'source_work_sha256': sha256(path.stem.encode()).hexdigest(),
                    'source_record_sha256': sha256(raw).hexdigest(),
                    'request_shape_sha256': _request_shape_sha256(record),
                    'queue_status': work_status.upper(),
                    'result_evidence_count': len(record.get('result_evidence_refs', [])),
                    'source_is_first_party_work_record': True,
                    'quality_gold_label_present': False,
                })
    reviews = []
    for name, statuses in evidence_by_name.items():
        sample = []
        for state in ('done', 'blocked', 'failed'):
            seen_state_shapes = set()
            for row in sorted(statuses[state], key=lambda item: item['source_work_sha256']):
                if row['request_shape_sha256'] in seen_state_shapes:
                    continue
                sample.append(row)
                seen_state_shapes.add(row['request_shape_sha256'])
                if len(seen_state_shapes) >= (10 if state == 'done' else 5):
                    break
        all_shapes = {row['request_shape_sha256'] for state_rows in statuses.values()
                      for row in state_rows}
        scope_type, scope_value = EVIDENCE_SCOPES[name]
        reviews.append({
            'name': name, 'selection_scope': scope_type, 'selection_value': scope_value,
            'source_status_counts': {k: len(v) for k, v in statuses.items()},
            'distinct_historical_request_shapes': len(all_shapes),
            'sampled_distinct_request_shapes': len({row['request_shape_sha256'] for row in sample}),
            'sample': sample, 'independently_labelled_case_count': 0,
            'agent_baseline_outputs_available': False,
            'agent_candidate_outputs_available': False,
            'evidence_quality_independently_verified': False,
            'quality_holdout_ready': False,
            'note': 'DONE/BLOCKED/FAILED records are queue states, not independent quality labels or commercial outcomes',
        })
    return reviews




def verify_selected_work_sources(case_inventory: list[dict], repo_root: Path = ROOT) -> dict:
    """Re-hash underlying canonical work; flag weak sources without inventing labels.

    Only safe repo-local canonical work JSON is read. External data references are
    deliberately not dereferenced; source receipt authenticity remains unverified.
    """
    refs = {}
    base = repo_root / 'runtime/departments/work'
    for state in ('done', 'blocked', 'failed'):
        directory = base / state
        if directory.is_symlink() or not directory.is_dir():
            continue
        for p in directory.glob('dept_work_*.json'):
            if not p.is_symlink() and p.is_file():
                refs[sha256(p.stem.encode()).hexdigest()] = (p, state)
    classifications = []
    counts = {'cases': 0, 'source_digest_verified': 0,
              'missing_source_or_digest_mismatch': 0,
              'positive_with_result_refs_no_error': 0,
              'negative_missing_result_refs': 0,
              'negative_with_result_refs': 0,
              'negative_cases_needing_independent_label': 0,
              'any_case_with_error': 0}
    for review in case_inventory:
        for sampled in review['sample']:
            counts['cases'] += 1
            chosen = refs.get(sampled['source_work_sha256'])
            source_verified = False
            kind = 'missing_or_changed_source'
            missing_output_refs = True
            error = True
            if chosen is not None:
                p, state = chosen
                original = p.read_bytes()
                source_verified = (
                    len(original) <= 256_000
                    and sha256(original).hexdigest() == sampled['source_record_sha256']
                    and state.upper() == sampled['queue_status']
                )
                if source_verified:
                    try:
                        work = json.loads(original)
                    except (ValueError, UnicodeError):
                        source_verified = False
                    else:
                        source_verified = (isinstance(work, dict) and work.get('id') == p.stem
                                           and work.get('status') == state.upper()
                                           and _request_shape_sha256(work) == sampled.get('request_shape_sha256'))
                        if source_verified:
                            output_refs = work.get('result_evidence_refs')
                            missing_output_refs = not isinstance(output_refs, list) or not output_refs
                            error = bool(work.get('error'))
            if source_verified:
                counts['source_digest_verified'] += 1
                counts['any_case_with_error'] += int(error)
                if sampled['queue_status'] == 'DONE' and not missing_output_refs and not error:
                    kind = 'positive_source_review_candidate_not_gold_label'
                    counts['positive_with_result_refs_no_error'] += 1
                elif sampled['queue_status'] != 'DONE':
                    kind = 'negative_source_review_candidate_not_gold_label'
                    counts['negative_cases_needing_independent_label'] += 1
                    if missing_output_refs:
                        counts['negative_missing_result_refs'] += 1
                    else:
                        counts['negative_with_result_refs'] += 1
                else:
                    kind = 'positive_source_incomplete_or_error'
            else:
                counts['missing_source_or_digest_mismatch'] += 1
            classifications.append({
                'skill_name': review['name'],
                'source_work_sha256': sampled['source_work_sha256'],
                'canonical_source_hash_matches': source_verified,
                'result_evidence_ref_present': source_verified and not missing_output_refs,
                'canonical_record_error_present': error if source_verified else None,
                'selection_class': kind,
                'independent_gold_label': None,
                'paired_agent_outputs_available': False,
                'independent_source_receipt_readback': False,
            })
    return {'counts': counts, 'cases': classifications,
            'all_source_digests_verified': counts['source_digest_verified'] == counts['cases'],
            'holdout_quality_verified': False, 'independent_label_count': 0,
            'external_actions': False, 'execution_authority': 'none'}


def inspect() -> dict:
    original = TRUST.read_bytes()
    registry = read_trust_registry(TRUST)
    names = sorted({name for _, group in PORTFOLIO_TASK_SKILLS.values() for name in group})
    rows = []
    temporary_pins = {}
    for name in names:
        p = LIBRARY / name / 'SKILL.md'
        body = p.read_text(encoding='utf-8')
        digest = sha256(p.read_bytes()).hexdigest()
        source_state = git_file_state(p)
        licence = licence_status(p.parent, body)
        static = evaluate_skill(name)
        advisory = review_local_skill(name)
        review_ok = (source_state == 'tracked_clean'
                     and licence == 'empire_internal_restricted_redistribution'
                     and static['passed'] and len(p.read_bytes()) <= MAX_AGENT_SKILL_BYTES
                     and name.startswith('empire-'))
        if review_ok:
            temporary_pins[name] = {'sha256': digest, 'status': 'approved'}
        pin = registry.get('approved_skills', {}).get(name, {})
        accepted_source = (
            name.startswith('empire-')
            or (name in {'frontend-design','webapp-testing'}
                and licence == 'apache_2_0_documented'
                and isinstance(pin, dict) and pin.get('licence') == 'Apache-2.0')
        )
        content_trusted = (isinstance(pin, dict) and pin.get('status') == 'approved'
                           and pin.get('sha256') == digest and accepted_source
                           and pin.get('trust_scope') == 'advisory_instruction_only')
        rows.append({'name': name, 'sha256': digest, 'source_state': source_state,
                     'licence': licence, 'static_contract_pass': bool(static['passed']),
                     'manual_review_status': advisory['status'],
                     'in_memory_test_eligible': review_ok,
                     'production_approval': content_trusted,
                     'trust_scope': pin.get('trust_scope') if content_trusted else None,
                     'independent_skill_quality_verified': False,
                     'decision': ('CONTENT_TRUST_PINNED_QUALITY_UNVERIFIED' if content_trusted
                                  else 'TEST_IN_MEMORY_ONLY' if review_ok else 'HOLD')})
    simulated = {'schema_version': 'empire.skill_trust.v1', 'approved_skills': temporary_pins}
    workflows = []
    for component, department in LANES.items():
        item = {'id': 'preview', 'department_keys': [department], 'target_component': component}
        chosen = recommend_work_item_skills(item)
        context = load_work_item_skill_context(item, registry=simulated)
        assert chosen['execution_authority'] == 'none'
        assert context['execution_authority'] == 'none' and context['scripts_executed'] is False
        workflows.append({'component': component, 'department': department,
                          'selected': [x['name'] for x in chosen['skill_recommendations'][0]['skills']],
                          'in_memory_loaded': [x['name'] for x in context['skills']],
                          'held': context['rejected']})
    live = json.loads(DISPATCH.read_text(encoding='utf-8'))
    originals = live.get('items', [])
    work_sample = []
    for item in originals:
        work = {'id': item.get('work_id', ''), 'department_keys': item['departments'],
                'target_component': item['target_component']}
        advice = recommend_work_item_skills(work)
        context = load_work_item_skill_context(work, registry=simulated)
        assert context['execution_authority'] == 'none' and context['scripts_executed'] is False
        work_sample.append({'component': item['target_component'], 'work_state': item['work_state'],
                            'selected_skill_count': sum(len(r.get('skills', [])) for r in advice['skill_recommendations']),
                            'in_memory_loaded_count': len(context['skills']),
                            'held_count': len(context['rejected'])})
    source_review = verify_selected_work_sources(real_evidence_review_inventory())
    actual_promotion_preflight = []
    for name in sorted(temporary_pins):
        preflight = promotion_preflight(name, trust_registry=TRUST)
        actual_promotion_preflight.append({
            'name': name, 'source_sha256': preflight['skill_sha256'],
            'status': preflight['status'], 'blocks': preflight['blocks'],
            'founder_approval_recorded': preflight['founder_approval_recorded'],
            'independent_performance_verified': preflight['independent_performance_verified'],
            'promoted': preflight['promoted'],
            'required_reviews': preflight['required_reviews'],
        })
    assert TRUST.read_bytes() == original, 'production trust registry changed'
    pinned = sum(row['production_approval'] for row in rows)
    status = ('ADVISORY_CONTENT_TRUST_ACTIVE_INDEPENDENT_QUALITY_HOLD' if pinned
              else 'ISOLATED_RESEARCH_PREVIEW_NOT_APPROVED_NOT_LIVE')
    return {'schema_version': 'empire.enterprise.skill_security_preview.v1',
            'status': status,
            'mode': 'OBSERVE', 'execution_authority': 'none', 'scripts_executed': False,
            'production_registry_unchanged': True,
            'production_approved_skill_count': len(registry.get('approved_skills', {})),
            'exact_digest_content_trust_count': pinned,
            'production_agent_execution_verified': False,
            'candidate_count': len(rows), 'in_memory_eligible_count': len(temporary_pins),
            'candidates': rows, 'portfolio_workflow_checks': workflows,
            'snapshot_work_item_count': len(work_sample), 'existing_work_item_checks': work_sample,
            'real_evidence_review_inventory': real_evidence_review_inventory(),
            'source_integrity_and_review_readiness': source_review,
            'canonical_promotion_preflight': actual_promotion_preflight,
            'founder_exact_digest_approval_recorded': False,
            'independent_holdout_verification_complete': False,
            'independent_tenant_privacy_review_complete': False,
            'production_skill_activation_verified': False}


if __name__ == '__main__':
    print(json.dumps(inspect(), sort_keys=True, indent=2))
