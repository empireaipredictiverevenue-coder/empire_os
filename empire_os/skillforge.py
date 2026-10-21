"""Empire SkillForge: sovereign, read-only skill catalogue and review inventory."""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path
from datetime import datetime, timezone
from empire_os.skill_exchange import SKILLS_ROOT, SAFE_NAME, TASK_SKILLS
from empire_os.skill_review import review_local_skill
from empire_os.skill_trust import SkillTrustError, read_trust_registry
from empire_os.skillforge_learning import learning_index
from empire_os.skillforge_harness2_bridge import skillforge_harness2_candidate
from empire_os.skillforge_proposals import proposal_history
from empire_os.okf_adapter import list_private_research


def catalogue(*, root: Path = SKILLS_ROOT, registry_path: Path | None = None,
              repo_root: Path | None = None,
              okf_bundle_path: Path | None = None) -> dict:
    """Inventory Empire-authored skills; registry approvals are never inferred."""
    registry = None
    if registry_path is not None:
        try:
            registry = read_trust_registry(registry_path)
        except SkillTrustError:
            pass
    approvals = registry.get('approved_skills', {}) if isinstance(registry, dict) else {}
    if not isinstance(approvals, dict):
        approvals = {}
    skills = []
    for path in sorted(root.glob('empire-*/SKILL.md')):
        name = path.parent.name
        if not SAFE_NAME.fullmatch(name) or path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            continue
        review = review_local_skill(name, root=root)
        if review['status'] == 'blocked':
            continue
        digest = sha256(path.read_bytes()).hexdigest()
        approval = approvals.get(name, {})
        approved = isinstance(approval, dict) and approval.get('status') == 'approved' and approval.get('sha256') == digest
        tasks = [task for task, (_, names) in TASK_SKILLS.items() if name in names]
        skills.append({'name': name, 'sha256': digest, 'tasks': tasks,
                       'trust': 'approved_pinned' if approved else 'candidate_not_approved',
                       'review_reasons': review['reasons'], 'execution_authority': 'none'})
    # The canonical SkillForge review path supports up to 5,000 original
    # observations. The older 500-row default is only a quick summary and
    # would falsely label a 1,000+ observation production audit incomplete.
    learning = (learning_index(repo_root, max_observations=5000)
                if repo_root is not None else None)
    review_queue = proposal_history(repo_root) if repo_root is not None else None
    okf_research = None
    if okf_bundle_path is not None:
        try:
            okf_research = list_private_research(
                okf_bundle_path, now=datetime.now(timezone.utc),
            )
        except Exception as exc:
            okf_research = {
                'status': 'unavailable', 'reason': type(exc).__name__,
                'research_only': True, 'execution_authority': 'none',
            }
    return {'product': 'Empire SkillForge', 'schema_version': 'empire.skillforge.catalogue.v1',
            'mode': 'OBSERVE', 'skills': skills, 'skill_count': len(skills),
            'approved_count': sum(s['trust'] == 'approved_pinned' for s in skills),
            'learning': learning,
            'review_queue': review_queue,
            'harness2_guard_candidate': (skillforge_harness2_candidate(repo_root)
                                         if repo_root is not None else None),
            'okf_research': okf_research,
            'external_download': False, 'execution_authority': 'none'}
