"""Governed local-only task-to-skill discovery; no execution or downloads."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
from empire_os.skills_library import SKILLS_ROOT

SAFE_NAME = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$')
# Empire-owned instructions only; legacy third-party skills remain discoverable
# through the original library, but are not automatically selected for tasks.
TASK_SKILLS = {
    'entity_resolution': ('intelligence', ('empire-identity-resolution',)),
    'evidence_analysis': ('intelligence', ('empire-evidence-verification',)),
    'lead_generation': ('lead_generation', ('empire-lead-research',)),
    'seo_research': ('seo', ('empire-seo-intelligence',)),
    'commercial_reply': ('sales', ('empire-reply-triage',)),
    'predictive_forecast': ('predictive', ('empire-forecast-validation',)),
    'revenue_reconciliation': ('finance', ('empire-revenue-reconciliation',)),
    'engineering_review': ('engineering', ('empire-engineering-verification',)),
    'revenue_readiness': ('sales', ('empire-revenue-readiness',)),
    'skill_authoring': ('innovator', ('empire-skill-authoring',)),
    'product_catalog_verification': ('product', ('empire-product-catalog-verification',)),
    'fulfilment_verification': ('operations_fulfilment', ('empire-fulfilment-verification',)),
    'email_drafting': ('email', ('empire-commercial-email-copy',)),
}


@dataclass(frozen=True)
class SkillMatch:
    name: str
    path: str
    status: str = 'local_candidate_not_authorized'


def discover_task_skills(task: str, *, root: Path = SKILLS_ROOT) -> dict:
    """Return local SKILL.md paths, never instructions or execution authority."""
    if task not in TASK_SKILLS:
        return {'task': task, 'status': 'unmapped_task', 'skills': [], 'execution_authority': 'none'}
    role, preferred = TASK_SKILLS[task]
    names = dict.fromkeys(preferred)
    found = []
    for name in names:
        if not SAFE_NAME.fullmatch(name):
            continue
        candidate = root / name / 'SKILL.md'
        # Do not follow symlinks outside the approved local library.
        if candidate.is_file() and candidate.resolve().is_relative_to(root.resolve()):
            content = candidate.read_bytes()
            found.append({**SkillMatch(name, str(candidate)).__dict__,
                          "sha256": sha256(content).hexdigest(),
                          "bytes": len(content)})
    return {'task': task, 'department_role': role, 'status': 'local_candidates' if found else 'missing_local_skills',
            'skills': found, 'execution_authority': 'none', 'external_download': False}

# Explicit capability mapping: no fuzzy keyword inference may expand authority.
DEPARTMENT_TASKS = {
    'sales': 'commercial_reply', 'closer': 'commercial_reply',
    'sales_revenue': 'commercial_reply',
    'email': 'email_drafting', 'copywriting': 'email_drafting',
    'lead_generation': 'lead_generation', 'acquisition': 'lead_generation',
    'seo': 'seo_research', 'marketing': 'seo_research',
    'marketing_growth': 'seo_research',
    'finance': 'revenue_reconciliation', 'revenue': 'revenue_reconciliation',
    'finance_capital': 'revenue_reconciliation',
    'engineering': 'engineering_review', 'devops': 'engineering_review',
    'quality_assurance': 'engineering_review',
    'research': 'evidence_analysis', 'intelligence': 'evidence_analysis',
    'market_intelligence': 'evidence_analysis',
    'strategy_executive': 'evidence_analysis',
    'predictive': 'predictive_forecast', 'predictive_revenue': 'predictive_forecast',
    'data': 'evidence_analysis', 'data_quant': 'predictive_forecast',
    'rd_innovation': 'skill_authoring',
    'product': 'product_catalog_verification',
    'product_verification': 'product_catalog_verification',
    'operations_fulfilment': 'fulfilment_verification',
    'fulfilment': 'fulfilment_verification',
}

# Exact target-component allowlist has precedence over broad department aliases.
# No substring/fuzzy matching: user-controlled task text cannot expand authority.
COMPONENT_TASKS = {
    'commercial_product_catalog': 'product_catalog_verification',
    'campaign_revenue_readiness': 'revenue_readiness',
    'predictive_cloud_opportunity_loop': 'predictive_forecast',
    'predictive_intelligence': 'predictive_forecast',
    'predictive_cloud_status': 'predictive_forecast',
    'identity_enrichment': 'entity_resolution',
    'buyer_capacity_readiness': 'evidence_analysis',
    'agent_tool_execution_plane': 'engineering_review',
    'commercial_reply_classification': 'commercial_reply',
}



def recommend_work_item_skills(work_item: dict, *, root: Path = SKILLS_ROOT) -> dict:
    """Read-only advice for an existing department work item, not dispatch."""
    if not isinstance(work_item, dict):
        raise ValueError('work item must be an object')
    departments = work_item.get('department_keys')
    if not isinstance(departments, (list, tuple)) or any(not isinstance(d, str) for d in departments):
        raise ValueError('invalid department keys')
    component = work_item.get('target_component')
    if component is not None and not isinstance(component, str):
        raise ValueError('invalid target component')
    component_task = COMPONENT_TASKS.get(component) if component is not None else None
    recommendations = []
    for department in dict.fromkeys(departments):
        task = component_task or DEPARTMENT_TASKS.get(department.strip().lower().replace('-', '_'))
        if task:
            recommendations.append({
                'department': department,
                'selection_basis': 'component_allowlist' if component_task else 'department_allowlist',
                **discover_task_skills(task, root=root),
            })
        else:
            recommendations.append({'department': department, 'status': 'unmapped_department', 'skills': []})
    return {'work_id': str(work_item.get('id') or ''), 'mode': 'OBSERVE',
            'execution_authority': 'none', 'skill_recommendations': recommendations,
            'queue_mutated': False, 'external_download': False}
