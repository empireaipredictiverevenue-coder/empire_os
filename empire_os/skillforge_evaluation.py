"""Deterministic, side-effect-free SkillForge candidate evaluation."""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path
from typing import Any
from empire_os.skill_exchange import SAFE_NAME, SKILLS_ROOT
from empire_os.skill_review import review_local_skill


def evaluate_skill(name: str, *, root: Path = SKILLS_ROOT,
                   expected_sha256: str | None = None) -> dict[str, Any]:
    """Review a pinned instruction candidate, not agent quality or permission."""
    if not isinstance(name, str) or not SAFE_NAME.fullmatch(name):
        return {'name': str(name), 'passed': False, 'reasons': ['invalid_name'], 'authority': 'none'}
    review = review_local_skill(name, root=root)
    if review['status'] == 'blocked':
        return {'name': name, 'passed': False, 'reasons': review['reasons'], 'authority': 'none'}
    path = root / name / 'SKILL.md'
    content = path.read_bytes()
    digest = sha256(content).hexdigest()
    reasons = []
    if not name.startswith('empire-'):
        reasons.append('not_empire_namespaced')
    if expected_sha256 is not None and digest != expected_sha256:
        reasons.append('digest_mismatch')
    text = content.decode('utf-8')
    for marker in ('## Evidence contract', 'authority', 'license:'):
        if marker.lower() not in text.lower():
            reasons.append('missing_' + marker.lower().replace(' ', '_').replace('#', '').strip('_'))
    if any(x in text.lower() for x in ('ignore previous instructions', 'disable safety checks')):
        reasons.append('unsafe_instruction_pattern')
    return {'name': name, 'sha256': digest, 'passed': not reasons,
            'reasons': reasons, 'review_reasons': review['reasons'],
            'evaluation_kind': 'static_contract_only',
            'agent_quality_verified': False, 'approved': False, 'authority': 'none'}


def compare_skill_versions(name: str, previous: bytes, current: bytes) -> dict[str, Any]:
    """Pure digest history record; does not imply improvement."""
    if not isinstance(name, str) or not SAFE_NAME.fullmatch(name):
        raise ValueError('invalid_skill_name')
    before = sha256(previous).hexdigest()
    after = sha256(current).hexdigest()
    return {'name': name, 'previous_sha256': before, 'current_sha256': after,
            'changed': before != after, 'improved': None, 'approval_carried_forward': False}
