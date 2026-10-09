"""Explicit Empire SkillForge approval for Empire Coder skill documents."""
from __future__ import annotations
from pathlib import Path, PurePosixPath
from empire_os.skill_trust import SkillTrustError, load_pinned_skill, read_trust_registry


def trusted_coder_skill(workspace: str | Path, relative_path: str) -> dict | None:
    """Return verified skill metadata/body, or deny. No third-party fallback."""
    if not isinstance(relative_path, str) or '\\' in relative_path:
        return None
    parts = PurePosixPath(relative_path).parts
    if (len(parts) != 5 or parts[:3] != ('empire_os', 'skills_library', 'skills')
        or parts[-1] != 'SKILL.md' or not parts[3].startswith('empire-')):
        return None
    root = Path(workspace).resolve()
    library = root / 'empire_os/skills_library/skills'
    registry_path = root / 'config/skill_trust_registry.json'
    try:
        registry = read_trust_registry(registry_path)
        return load_pinned_skill(parts[3], root=library, registry=registry)
    except (SkillTrustError, OSError, ValueError):
        return None
