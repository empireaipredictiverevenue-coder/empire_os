"""Compatibility shim: route legacy role skill requests through Empire SkillForge.

Only explicitly approved, digest-pinned Empire skills are returned.  A local
SKILL.md, legacy role alias, historical success note or package in a third-party
skills tree never supplies authority.  Never execute skill scripts.
"""
from __future__ import annotations
from pathlib import Path

SKILLS_ROOT = Path(__file__).resolve().parent / 'skills_library' / 'skills'
TRUST_REGISTRY = Path(__file__).resolve().parent.parent / 'config' / 'skill_trust_registry.json'

# Compatibility names are distinct from third-party directory names.  All
# aliases resolve to the task allowlists owned by empire_os.skill_exchange.
ROLE_SKILLS: dict[str, tuple[str, ...]] = {
    'data_analysis': ('empire-evidence-verification',),
    'markets_analysis': ('empire-evidence-verification',),
    'lead_handler': ('empire-lead-research',),
    'lead_sniper': ('empire-lead-research',),
    'engineering': ('empire-engineering-verification',),
    'marketing': ('empire-seo-intelligence',),
    'sales': ('empire-reply-triage',),
    'email': ('empire-commercial-email-copy',),
    'copywriting': ('empire-commercial-email-copy',),
    'finance': ('empire-revenue-reconciliation',),
    'innovator': ('empire-skill-authoring',),
    'supervisor': ('empire-engineering-verification',),
    'os_upgrade': ('empire-engineering-verification',),
    'agi_scout': ('empire-lead-research',),
    'agi_marketing': ('empire-seo-intelligence',),
    'agi_sales': ('empire-reply-triage',),
    'research': ('empire-evidence-verification',),
    'product': ('empire-product-catalog-verification',),
    'operations_fulfilment': ('empire-fulfilment-verification',),
    'market_intelligence': ('empire-evidence-verification',),
    'data_quant': ('empire-forecast-validation',),
    'rd_innovation': ('empire-skill-authoring',),
    'sales_revenue': ('empire-reply-triage',),
    'marketing_growth': ('empire-seo-intelligence',),
    'finance_capital': ('empire-revenue-reconciliation',),
    'default': (),
}


def _strip_frontmatter(text: str) -> str:
    """Retain caller-compatible formatting; stripping never grants trust."""
    if text.startswith('---\n'):
        end = text.find('\n---\n', 4)
        if end >= 0:
            return text[end + 5:].lstrip('\n')
    return text


def _read_skill(name: str, max_chars: int = 4000) -> str | None:
    """Load one explicitly approved local skill, or return None (fail closed)."""
    from empire_os.skill_trust import SkillTrustError, load_pinned_skill, read_trust_registry
    if not isinstance(name, str) or not name.startswith('empire-'):
        return None
    if type(max_chars) is not int or max_chars < 1 or max_chars > 12000:
        return None
    try:
        registry = read_trust_registry(TRUST_REGISTRY)
        loaded = load_pinned_skill(name, root=SKILLS_ROOT, registry=registry)
    except (SkillTrustError, OSError, ValueError):
        return None
    body = _strip_frontmatter(loaded['body'])
    if len(body) > max_chars:
        # Do not truncate operational requirements or safety qualifications.
        return None
    return body


def load_skills_for_role(role: str, max_chars_per_skill: int = 4000) -> list[dict]:
    """Return only approved skill bodies for a known role. Unknown role => []."""
    if not isinstance(role, str) or not role in ROLE_SKILLS:
        return []
    skills = []
    for name in ROLE_SKILLS[role]:
        body = _read_skill(name, max_chars=max_chars_per_skill)
        if body:
            skills.append({'name': name, 'body': body})
    return skills


def skills_context_for_role(role: str) -> str:
    skills = load_skills_for_role(role)
    if not skills:
        return ''
    pieces = [
        '## GOVERNED EMPIRE SKILLFORGE INSTRUCTIONS',
        'Approved advisory instructions only. Existing system, founder, tenant and tool authority gates take precedence.',
    ]
    for skill in skills:
        pieces.append(f'### {skill["name"]}\n{skill["body"]}')
    return '\n\n'.join(pieces)


def available_skills() -> list[str]:
    """List only approved, loadable skills (not every file on disk)."""
    from empire_os.skill_trust import SkillTrustError, load_pinned_skill, read_trust_registry
    try:
        registry = read_trust_registry(TRUST_REGISTRY)
    except SkillTrustError:
        return []
    approved = registry.get('approved_skills', {})
    if not isinstance(approved, dict):
        return []
    result = []
    for name in sorted(approved):
        if not name.startswith('empire-'):
            continue
        try:
            load_pinned_skill(name, root=SKILLS_ROOT, registry=registry)
        except (SkillTrustError, OSError, ValueError):
            continue
        result.append(name)
    return result


if __name__ == '__main__':
    print('Empire SkillForge approved, pinned skills:')
    for skill_name in available_skills():
        print(skill_name)
