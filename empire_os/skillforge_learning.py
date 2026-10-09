"""Capture reusable *candidate* techniques from canonical completed work.

No automatic skill publication, script execution, permissions or raw result data.
"""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any

WORK_ID = re.compile(r'^dept_work_[0-9a-f]{24}$')
SAFE_COMPONENT = re.compile(r'^[a-z][a-z0-9_]{0,79}$')
MAX_RECORD = 256_000


def capture_completed_work(repo_root: str | Path, work_id: str) -> dict[str, Any]:
    """Store one append-only, redacted draft per evidenced canonical DONE item.

    Returned status is explicitly NOT an approval or production skill.
    """
    if not isinstance(work_id, str) or not WORK_ID.fullmatch(work_id):
        return {'status': 'skipped', 'reason': 'invalid_work_id', 'approved': False}
    root = Path(repo_root).resolve()
    path = root / 'runtime/departments/work/done' / (work_id + '.json')
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_RECORD:
        return {'status': 'skipped', 'reason': 'canonical_done_work_missing', 'approved': False}
    try:
        item = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, ValueError):
        return {'status': 'skipped', 'reason': 'invalid_done_record', 'approved': False}
    if not isinstance(item, dict) or item.get('id') != work_id or item.get('status') != 'DONE':
        return {'status': 'skipped', 'reason': 'not_canonical_done', 'approved': False}
    if item.get('authority') not in ('observe', 'internal_write') or item.get('error'):
        return {'status': 'skipped', 'reason': 'unsafe_work_status', 'approved': False}
    refs = item.get('result_evidence_refs')
    result = item.get('result')
    component = item.get('target_component')
    if not isinstance(refs, list) or not refs or any(not isinstance(r, str) or not r.strip() for r in refs):
        return {'status': 'skipped', 'reason': 'missing_completion_evidence', 'approved': False}
    if not isinstance(result, dict) or not result or not isinstance(component, str) or not SAFE_COMPONENT.fullmatch(component):
        return {'status': 'skipped', 'reason': 'untrusted_work_contract', 'approved': False}
    if result.get('execution_authority') not in (None, 'none') or result.get('simulated') is True or result.get('shadow_only') is True:
        return {'status': 'skipped', 'reason': 'unsupported_result_authority', 'approved': False}
    adapter = result.get('adapter')
    if not isinstance(adapter, str) or not SAFE_COMPONENT.fullmatch(adapter):
        return {'status': 'skipped', 'reason': 'unverified_adapter', 'approved': False}
    source_id = sha256(work_id.encode('utf-8')).hexdigest()
    result_digest = sha256(json.dumps(result, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()
    evidence_hashes = sorted(set(sha256(ref.encode('utf-8')).hexdigest() for ref in refs))
    candidate_id = 'skill_observation_' + sha256((source_id + ':' + ','.join(evidence_hashes)).encode()).hexdigest()[:32]
    draft = {
        'schema_version': 'empire.skillforge.observation.v1',
        'candidate_id': candidate_id,
        'status': 'DRAFT_REVIEW_REQUIRED',
        'approved': False,
        'skill_available_to_agents': False,
        'execution_authority': 'none',
        'observation_kind': 'completed_department_work',
        'source_work_sha256': source_id,
        'source_result_sha256': result_digest,
        'success_claim': 'canonical_work_marked_DONE_only',
        'repeatability_verified': False,
        'source_evidence_sha256': evidence_hashes,
        'evidence_count': len(refs),
        'proposed_skill_name': 'empire-learned-' + component.replace('_', '-'),
        'component': component,
        'adapter': adapter,
        'review_requirements': [
            'inspect_canonical_outcome_and_source_evidence',
            'confirm_generalizable_success_not_merely_queue_completion',
            'redact_private_data_and_screen_prompt_injection',
            'author_a_bounded_skill_with_reproducible_tests',
            'review_licence_security_and_tenant_boundaries',
            'explicitly_approve_content_digest_before_loading',
        ],
        'generated_at': datetime.now(timezone.utc).isoformat(),
    }
    directory = root / 'runtime/skillforge/observations'
    if directory.is_symlink():
        raise ValueError('unsafe_skillforge_directory')
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError('unsafe_skillforge_directory')
    os.chmod(directory, 0o700)
    target = directory / (candidate_id + '.json')
    payload = (json.dumps(draft, sort_keys=True, indent=2) + '\n').encode('utf-8')
    try:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    except FileExistsError:
        return {'status': 'existing_candidate', 'candidate_id': candidate_id, 'approved': False}
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return {'status': 'candidate_saved', 'candidate_id': candidate_id, 'approved': False}


def _verified_learning_observations(repo_root: str | Path, *, max_observations: int = 500) -> tuple[list[dict[str, Any]], int, int]:
    """Revalidate every observation against immutable-looking canonical DONE evidence.

    The work queue still owns completion truth; this function grants no skill trust.
    """
    if isinstance(max_observations, bool) or not isinstance(max_observations, int) or not 1 <= max_observations <= 5000:
        raise ValueError('invalid_observation_limit')
    root = Path(repo_root).resolve()
    directory = root / 'runtime/skillforge/observations'
    if not directory.exists():
        return [], 0, 0
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError('invalid_skillforge_observation_directory')
    files = sorted(directory.glob('skill_observation_*.json'))
    done_directory = root / 'runtime/departments/work/done'
    work_paths: dict[str, Path] = {}
    if done_directory.is_dir() and not done_directory.is_symlink():
        for done_path in done_directory.glob('dept_work_*.json'):
            if WORK_ID.fullmatch(done_path.stem) and not done_path.is_symlink():
                work_paths[sha256(done_path.stem.encode('utf-8')).hexdigest()] = done_path
    valid: list[dict[str, Any]] = []
    invalid = 0
    seen_work: set[str] = set()
    for path in files[:max_observations]:
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 64_000:
                raise ValueError('unsafe_observation')
            row = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(row, dict):
                raise ValueError('invalid_observation')
            source_id = row.get('source_work_sha256')
            done_path = work_paths.get(source_id) if isinstance(source_id, str) else None
            if done_path is None or done_path.stat().st_size > MAX_RECORD:
                raise ValueError('missing_canonical_done')
            work = json.loads(done_path.read_text(encoding='utf-8'))
            if (not isinstance(work, dict) or work.get('id') != done_path.stem
                or work.get('status') != 'DONE' or work.get('error')
                or work.get('authority') not in ('observe', 'internal_write')):
                raise ValueError('invalid_completion')
            result = work.get('result')
            refs = work.get('result_evidence_refs')
            component = work.get('target_component')
            if (not isinstance(result, dict) or not result
                or not isinstance(refs, list) or not refs
                or any(not isinstance(ref, str) or not ref.strip() for ref in refs)
                or not isinstance(component, str) or not SAFE_COMPONENT.fullmatch(component)):
                raise ValueError('invalid_completion_evidence')
            adapter = result.get('adapter')
            if (not isinstance(adapter, str) or not SAFE_COMPONENT.fullmatch(adapter)
                or result.get('execution_authority') not in (None, 'none')
                or result.get('simulated') is True or result.get('shadow_only') is True):
                raise ValueError('invalid_adapter_evidence')
            evidence_hashes = sorted(set(sha256(ref.encode('utf-8')).hexdigest() for ref in refs))
            expected_id = 'skill_observation_' + sha256((source_id + ':' + ','.join(evidence_hashes)).encode()).hexdigest()[:32]
            result_digest = sha256(json.dumps(result, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()
            if (row.get('schema_version') != 'empire.skillforge.observation.v1'
                or row.get('candidate_id') != expected_id or path.stem != expected_id
                or row.get('status') != 'DRAFT_REVIEW_REQUIRED'
                or row.get('approved') is not False
                or row.get('skill_available_to_agents') is not False
                or row.get('execution_authority') != 'none'
                or row.get('source_result_sha256') != result_digest
                or row.get('source_evidence_sha256') != evidence_hashes
                or row.get('component') != component or row.get('adapter') != adapter
                or row.get('evidence_count') != len(refs)
                or row.get('repeatability_verified') is not False):
                raise ValueError('observation_provenance_mismatch')
            if source_id in seen_work:
                raise ValueError('duplicate_canonical_work')
            seen_work.add(source_id)
            valid.append({'candidate_id': expected_id, 'source_work_sha256': source_id,
                          'component': component, 'adapter': adapter})
        except (OSError, ValueError, TypeError, UnicodeError, AttributeError):
            invalid += 1
            continue
    return valid, invalid, max(0, len(files) - max_observations)


def learning_index(repo_root: str | Path, *, max_observations: int = 500) -> dict[str, Any]:
    """Evidence-validated read-only inventory of candidates, never approvals."""
    valid, invalid, truncated = _verified_learning_observations(repo_root, max_observations=max_observations)
    by_technique: dict[tuple[str, str], dict[str, Any]] = {}
    for row in valid:
        key = (row['component'], row['adapter'])
        if key not in by_technique:
            by_technique[key] = {
                'component': key[0], 'adapter': key[1], 'observation_count': 0,
                'review_required': True, 'learned_skill_approved': False,
            }
        by_technique[key]['observation_count'] += 1
    return {'observation_count': len(valid), 'techniques': list(by_technique.values()),
            'invalid_observations': invalid, 'approval_authority': 'none',
            'inventory_truncated': bool(truncated)}
