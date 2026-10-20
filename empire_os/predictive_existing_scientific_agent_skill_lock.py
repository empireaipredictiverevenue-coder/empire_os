"""Pinned existing Scientific Research Agent skill-manifest adapter.

The original Scientific Research Agent implementation currently lives in an
untracked production-owner worktree, so an isolated immutable Predictive
Revenue release must NOT implicitly import/execute it from mutable production.
Reuse its existing six content-addressed skill *contracts*, without copying
its world-model algorithm, creating an alternative agent or making a result
from its synthetic benchmarks into customer/model authority.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCIENTIFIC_AGENT_SKILL_LOCK = {
    "evidence_verification": (
        "empire_os/skills_library/skills/empire-evidence-verification/SKILL.md",
        "f14e5ddd4eaaad69847ba7c9c15815a929e83b9ec244721a1a6f88362af86d9b",
        "governing_skill",
    ),
    "engineering_verification": (
        "empire_os/skills_library/skills/empire-engineering-verification/SKILL.md",
        "b750cc0f8578eb67e5f884fe1f07202e6984c1fbcb8a33cb91a05020308d67ec",
        "governing_skill",
    ),
    "world_model_architect": (
        "empire_os/data/prompts/agent_world_model_architect.txt",
        "7d1eda07df90c2a3599455f10dc08c72dd8f2b223ac8f21dd477858057598552",
        "reference_only",
    ),
    "paper_replication_harness": (
        "empire_os/data/prompts/scientific_paper_replication_harness_architect.txt",
        "de8e86b51dd2b3bc8b405b7577cad2d434a80a87346148d5ddbb017ba65bc422",
        "reference_only",
    ),
    "autonomous_ml_research": (
        "empire_os/data/prompts/autonomous_ml_research_agent.txt",
        "afe0805c9178f8f2f34d6e9da2d7a66940d98f8d9aee0b655df16c01c4c6884b",
        "DISABLED_unattended_loop_reference_only",
    ),
    "experiment_registry": (
        "empire_os/experiment_registry.py",
        "c1fb200d561a643395efa9d2bc5dc8e3cc8dc00c9816bdd6dc484984eb3c0aa1",
        "existing_code_contract",
    ),
}


def verify_existing_scientific_agent_skill_lock(*, root: Path = ROOT) -> dict[str, Any]:
    """Exact existing skill hashes in the audited release; no external import."""
    if (not isinstance(root, Path) or not root.is_dir()
            or root.is_symlink()):
        raise ValueError("valid immutable scientific skill checkout required")
    verified = []
    for name, (relative, expected, role) in SCIENTIFIC_AGENT_SKILL_LOCK.items():
        fragment = Path(relative)
        if fragment.is_absolute() or ".." in fragment.parts:
            raise ValueError("unsafe scientific skill path")
        path = root / fragment
        if (not path.is_file() or path.is_symlink()
                or any((root / Path(*fragment.parts[:i])).is_symlink()
                       for i in range(1, len(fragment.parts)))):
            raise ValueError("missing or unsafe scientific skill")
        data = path.read_bytes()
        if not 20 < len(data) < 200_000 or sha256(data).hexdigest() != expected:
            raise ValueError("existing scientific skill integrity mismatch")
        verified.append({"skill": name, "sha256": expected, "use": role})
    return {
        "schema_version": "empire.agi.scientific_skill_custody.v1",
        "status": "PINNED_EXISTING_SKILLS_VERIFIED",
        "existing_contracts": verified,
        "scientific_agent_core_runtime_loaded": False,
        "source_manifest_reused_not_scientific_agent_reimplemented": True,
        "prompt_text_executed": False,
        "autonomous_training_loop_enabled": False,
        "external_plugins_invoked": False,
        "execution_authority": "none",
    }
