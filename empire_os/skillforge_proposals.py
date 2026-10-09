"""Deterministic, review-only skill draft proposals from verified completed work.

This module may write private drafts under runtime/skillforge/proposals.  It never
changes the approved skill library, registry, department queue, or agent authority.
"""
from __future__ import annotations
from collections import defaultdict
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any

from empire_os.skillforge_learning import _verified_learning_observations

CHECKPOINTS = (3, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000)


def _proposal_specs(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    observations, invalid, truncated = _verified_learning_observations(root, max_observations=5000)
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in observations:
        groups[(row['component'], row['adapter'])].append(row)
    specs = []
    for (component, adapter), rows in sorted(groups.items()):
        count = len(rows)
        checkpoints = [n for n in CHECKPOINTS if n <= count]
        if not checkpoints:
            continue
        checkpoint = checkpoints[-1]
        seed = f'{component}|{adapter}|{checkpoint}'
        proposal_id = 'skill_proposal_' + sha256(seed.encode('utf-8')).hexdigest()[:24]
        source_ids = sorted(x['source_work_sha256'] for x in rows)
        observations_digest = sha256('\n'.join(source_ids).encode('utf-8')).hexdigest()
        specs.append({
            'proposal_id': proposal_id,
            'schema_version': 'empire.skillforge.proposal.v1',
            'status': 'DRAFT_REVIEW_REQUIRED',
            'proposed_skill_name': 'empire-learned-' + component.replace('_', '-'),
            'component': component,
            'adapter': adapter,
            'checkpoint': checkpoint,
            'evidenced_work_count': count,
            'observed_work_set_sha256': observations_digest,
            'approved': False,
            'agent_quality_verified': False,
            'repeatability_verified': False,
            'skill_available_to_agents': False,
            'execution_authority': 'none',
            'required_review': [
                'independently_verify_outcomes_not_just_done_status',
                'test_on_holdout_tasks_and_failure_cases',
                'check_tenant_privacy_and_security_controls',
                'check_instruction_injection_and_licence_provenance',
                'review_specific_procedure_and_claims',
                'separately_authorize_fingerprint_pinned_skill_if_approved',
            ],
        })
    return specs, {'verified_observations': len(observations),
                   'invalid_observations': invalid,
                   'inventory_truncated': bool(truncated)}


def _draft_markdown(spec: dict[str, Any]) -> str:
    """Produce a minimal safe *review template*, never assert learned expertise."""
    component = spec['component']
    adapter = spec['adapter']
    return (
        '---\n'
        f'name: {spec["proposed_skill_name"]}\n'
        'description: Unapproved internal draft from evidence-linked department work. NOT FOR AGENT LOADING.\n'
        'license: EmpireOS internal candidate; author and rights review required\n'
        '---\n\n'
        f'# Candidate: {component.replace("_", " ").title()}\n\n'
        '> **DRAFT ONLY — NOT APPROVED OR TESTED AS A REUSABLE SKILL.**\n\n'
        '## Observed context\n\n'
        f'- Existing department component: `{component}`\n'
        f'- Existing adapter: `{adapter}`\n'
        f'- Distinct evidenced work completions at capture: {spec["evidenced_work_count"]}\n'
        f'- Review checkpoint: {spec["checkpoint"]}\n'
        f'- Evidence-set fingerprint: `{spec["observed_work_set_sha256"]}`\n\n'
        '## Procedure to validate (not an instruction to execute)\n\n'
        '1. Inspect the existing authorized adapter contract and the corresponding canonical work evidence.\n'
        '2. Identify the exact repeatable procedure and its required inputs, outputs, and failure conditions.\n'
        '3. Run independent isolated holdout and negative tests against real task requirements.\n'
        '4. Compare outcomes with baseline; do not infer quality from DONE status or counts.\n'
        '5. Document the verified procedure, provenance, confidentiality controls, and remaining limits.\n\n'
        '## Governance\n\n'
        'No outbound, spending, funds, production changes, fulfilment or revenue recognition authority.\n'
        'No instructions in this draft may override higher-priority policy, approval gates, or tenant isolation.\n'
        'Approval requires review and a separately pinned digest in the EmpireOS trust registry.\n'
    )


def refresh_skill_proposals(repo_root: str | Path, *, apply: bool = False) -> dict[str, Any]:
    """Report or atomically save versioned draft proposals at observation milestones."""
    root = Path(repo_root).resolve()
    specs, audit = _proposal_specs(root)
    parent = root / 'runtime/skillforge/proposals'
    if (root / 'runtime/skillforge').is_symlink() or parent.is_symlink():
        raise ValueError('unsafe_skill_proposal_directory')
    if apply and (audit['invalid_observations'] or audit['inventory_truncated']):
        raise ValueError('skill_proposal_evidence_audit_incomplete')
    saved = 0
    existed = 0
    proposals = []
    for spec in specs:
        target = parent / spec['proposal_id']
        if target.is_symlink():
            raise ValueError('unsafe_existing_skill_proposal')
        if target.exists():
            if not target.is_dir() or any((target / n).is_symlink() or not (target / n).is_file()
                                          for n in ('manifest.json', 'SKILL.md')):
                raise ValueError('unsafe_existing_skill_proposal')
            try:
                stored = json.loads((target / 'manifest.json').read_text(encoding='utf-8'))
                expected_draft = _draft_markdown(stored)
                actual_draft = (target / 'SKILL.md').read_text(encoding='utf-8')
            except (OSError, ValueError, TypeError, KeyError, UnicodeError) as exc:
                raise ValueError('invalid_existing_skill_proposal') from exc
            if (not isinstance(stored, dict) or stored.get('proposal_id') != spec['proposal_id']
                or stored.get('component') != spec['component'] or stored.get('adapter') != spec['adapter']
                or stored.get('checkpoint') != spec['checkpoint']
                or stored.get('status') != 'DRAFT_REVIEW_REQUIRED'
                or stored.get('approved') is not False
                or stored.get('skill_available_to_agents') is not False
                or actual_draft != expected_draft):
                raise ValueError('tampered_existing_skill_proposal')
            existed += 1
            state = 'existing_review_draft'
        elif not apply:
            state = 'ready_for_review_draft'
        else:
            parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if parent.is_symlink() or not parent.is_dir():
                raise ValueError('unsafe_skill_proposal_directory')
            os.chmod(parent, 0o700)
            tmp = Path(tempfile.mkdtemp(prefix='.skillforge_staging_', dir=parent))
            try:
                for name, data in (
                    ('manifest.json', json.dumps(spec, indent=2, sort_keys=True) + '\n'),
                    ('SKILL.md', _draft_markdown(spec)),
                ):
                    output = tmp / name
                    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                        stream.write(data)
                        stream.flush()
                        os.fsync(stream.fileno())
                try:
                    tmp.rename(target)
                except OSError as exc:
                    if target.exists():
                        existed += 1
                        state = 'existing_review_draft'
                    else:
                        raise exc
                else:
                    saved += 1
                    state = 'review_draft_saved'
            finally:
                if tmp.exists():
                    shutil.rmtree(tmp)
        proposals.append({'id': spec['proposal_id'], 'component': spec['component'],
                          'adapter': spec['adapter'], 'checkpoint': spec['checkpoint'],
                          'evidenced_work_count': spec['evidenced_work_count'],
                          'status': state, 'approved': False})
    return {'product': 'Empire SkillForge', 'mode': 'OBSERVE',
            'execution_authority': 'none', 'apply': bool(apply),
            'review_drafts_saved': saved, 'existing_review_drafts': existed,
            'proposals': proposals, **audit}


def proposal_history(repo_root: str | Path, *, max_proposals: int = 200) -> dict[str, Any]:
    """Read-only private review inventory; never marks draft instructions trusted."""
    if isinstance(max_proposals, bool) or not isinstance(max_proposals, int) or not 1 <= max_proposals <= 5000:
        raise ValueError('invalid_proposal_limit')
    parent = Path(repo_root).resolve() / 'runtime/skillforge/proposals'
    if not parent.exists():
        return {'draft_count': 0, 'invalid_drafts': 0, 'drafts': [], 'approval_authority': 'none'}
    if parent.is_symlink() or not parent.is_dir():
        raise ValueError('unsafe_skill_proposal_directory')
    paths = sorted(parent.glob('skill_proposal_*'))
    drafts = []
    invalid = 0
    for folder in paths[:max_proposals]:
        try:
            if folder.is_symlink() or not folder.is_dir():
                raise ValueError('unsafe_draft_folder')
            metadata = folder / 'manifest.json'
            body = folder / 'SKILL.md'
            if (metadata.is_symlink() or body.is_symlink() or not metadata.is_file()
                or not body.is_file() or metadata.stat().st_size > 32_000
                or body.stat().st_size > 32_000):
                raise ValueError('unsafe_draft_contents')
            manifest = json.loads(metadata.read_text(encoding='utf-8'))
            content = body.read_text(encoding='utf-8')
            if (not isinstance(manifest, dict)
                or manifest.get('schema_version') != 'empire.skillforge.proposal.v1'
                or manifest.get('proposal_id') != folder.name
                or manifest.get('status') != 'DRAFT_REVIEW_REQUIRED'
                or manifest.get('approved') is not False
                or manifest.get('skill_available_to_agents') is not False
                or manifest.get('execution_authority') != 'none'
                or not isinstance(manifest.get('component'), str)
                or not isinstance(manifest.get('adapter'), str)
                or content != _draft_markdown(manifest)):
                raise ValueError('invalid_draft_provenance')
            drafts.append({'id': folder.name, 'component': manifest['component'],
                           'adapter': manifest['adapter'],
                           'checkpoint': manifest['checkpoint'],
                           'evidenced_work_count': manifest['evidenced_work_count'],
                           'content_sha256': sha256(content.encode('utf-8')).hexdigest(),
                           'review_required': True, 'approved': False,
                           'agent_quality_verified': False})
        except (OSError, ValueError, KeyError, TypeError, UnicodeError):
            invalid += 1
    return {'draft_count': len(drafts), 'invalid_drafts': invalid,
            'inventory_truncated': len(paths) > max_proposals,
            'drafts': drafts, 'approval_authority': 'none'}
