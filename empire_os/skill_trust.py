"""Explicit, pinned, local skill instruction loading; never execute skill scripts."""
from __future__ import annotations
import json
from hashlib import sha256
from pathlib import Path
from typing import Any
from empire_os.skill_exchange import SAFE_NAME, SKILLS_ROOT

MAX_SKILL_BYTES = 128_000
MAX_AGENT_SKILL_BYTES = 12_000
MAX_AGENT_CONTEXT_BYTES = 32_000

class SkillTrustError(ValueError):
    pass


def load_pinned_skill(name: str, *, root: Path = SKILLS_ROOT,
                      registry: dict[str, Any] | None = None) -> dict[str, Any]:
    """Load SKILL.md only if explicitly approved and content hash matches."""
    if not isinstance(name, str) or not SAFE_NAME.fullmatch(name):
        raise SkillTrustError('invalid_skill_name')
    if not isinstance(registry, dict) or registry.get('schema_version') != 'empire.skill_trust.v1':
        raise SkillTrustError('missing_trust_registry')
    approved = registry.get('approved_skills')
    if not isinstance(approved, dict):
        raise SkillTrustError('invalid_approved_skills')
    record = approved.get(name)
    if not isinstance(record, dict) or record.get('status') != 'approved':
        raise SkillTrustError('skill_not_approved')
    expected = record.get('sha256')
    if not isinstance(expected, str) or len(expected) != 64 or any(c not in '0123456789abcdef' for c in expected):
        raise SkillTrustError('invalid_approved_digest')
    path = root / name / 'SKILL.md'
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
        raise SkillTrustError('unsafe_skill_path')
    with path.open('rb') as stream:
        data = stream.read(MAX_SKILL_BYTES + 1)
    if len(data) > MAX_SKILL_BYTES:
        raise SkillTrustError('skill_too_large')
    if sha256(data).hexdigest() != expected:
        raise SkillTrustError('skill_digest_mismatch')
    try:
        body = data.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise SkillTrustError('skill_invalid_utf8') from exc
    return {'name': name, 'sha256': expected, 'body': body,
            'execution_authority': 'none', 'scripts_executed': False}


def read_trust_registry(path: Path) -> dict[str, Any]:
    """Read explicit approvals; missing registry is not implicit approval."""
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise SkillTrustError('trust_registry_unavailable') from exc
    if not isinstance(value, dict):
        raise SkillTrustError('invalid_trust_registry')
    return value


def load_work_item_skill_context(work_item: dict[str, Any], *,
                                 root: Path = SKILLS_ROOT,
                                 registry: dict[str, Any] | None = None,
                                 max_skills: int = 4) -> dict[str, Any]:
    """Build bounded agent context from explicitly pinned local skills only."""
    from empire_os.skill_exchange import recommend_work_item_skills
    if not isinstance(max_skills, int) or not 1 <= max_skills <= 8:
        raise SkillTrustError('invalid_skill_limit')
    advice = recommend_work_item_skills(work_item, root=root)
    selected = []
    rejected = []
    seen = set()
    context_bytes = 0
    for department in advice['skill_recommendations']:
        for candidate in department['skills']:
            name = candidate['name']
            if name in seen:
                continue
            seen.add(name)
            if len(selected) >= max_skills:
                rejected.append({'name': name, 'reason': 'skill_context_limit'})
                continue
            try:
                loaded = load_pinned_skill(name, root=root, registry=registry)
            except SkillTrustError as exc:
                rejected.append({'name': name, 'reason': str(exc)})
                continue
            skill_bytes = len(loaded['body'].encode('utf-8'))
            if skill_bytes > MAX_AGENT_SKILL_BYTES:
                rejected.append({'name': name, 'reason': 'skill_context_too_large'})
                continue
            if context_bytes + skill_bytes > MAX_AGENT_CONTEXT_BYTES:
                rejected.append({'name': name, 'reason': 'agent_skill_context_budget_exceeded'})
                continue
            context_bytes += skill_bytes
            selected.append(loaded)
    return {'work_id': advice['work_id'], 'mode': 'OBSERVE',
            'skills': selected, 'rejected': rejected, 'context_bytes': context_bytes,
            'execution_authority': 'none', 'scripts_executed': False}
