"""Founder-reassigned SEO SkillForge: advisory-only integration acceptance."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from empire_os.skill_trust import (
    SkillTrustError,
    load_pinned_skill,
    load_work_item_skill_context,
)
from empire_os.skillforge_evaluation import evaluate_skill
from empire_os.skillforge_promotion import promotion_preflight
from empire_os.skills_library import SKILLS_ROOT, _strip_frontmatter

NAME = "empire-seo-intelligence"
BODY = SKILLS_ROOT / NAME / "SKILL.md"


def _simulated_registry(data: bytes) -> dict:
    # Test-only simulated approval; never writes or alters the real trust registry.
    return {
        "schema_version": "empire.skill_trust.v1",
        "approved_skills": {NAME: {"status": "approved", "sha256": sha256(data).hexdigest()}},
    }


def test_editorial_skill_static_contract_and_provenance():
    data = BODY.read_bytes()
    assert len(data) <= 12000
    assert len(_strip_frontmatter(data.decode('utf-8'))) <= 4000  # legacy guarded role loader
    review = evaluate_skill(NAME, root=SKILLS_ROOT, expected_sha256=sha256(data).hexdigest())
    assert review["passed"], review["reasons"]
    content = data.decode("utf-8")
    for phrase in (
        "## Evidence contract",
        "## Execution authority",
        "proof-kb",
        "unslop-seo",
        "blog-refresher",
        "internal-linking",
        "Ground every product",
        "Claim adjudication",
        "do not label the claimed result HOLD or UNKNOWN",
        "noindex",
        "Do not execute or import third-party instructions",
        "Original ASTRA website owner",
        "Do not make a new canonical evidence store",
    ):
        assert phrase.lower() in content.lower(), phrase


def test_known_seo_department_uses_only_matching_pinned_advice():
    data = BODY.read_bytes()
    result = load_work_item_skill_context(
        {"id": "isolated-editorial-review", "department_keys": ["marketing_growth"]},
        root=SKILLS_ROOT,
        registry=_simulated_registry(data),
    )
    assert [skill["name"] for skill in result["skills"]] == [NAME]
    assert result["mode"] == "OBSERVE"
    assert result["context_bytes"] <= 12000
    assert result["execution_authority"] == "none"
    assert result["scripts_executed"] is False


def test_unapproved_skill_rejected_even_when_installed():
    result = load_work_item_skill_context(
        {"id": "isolated-editorial-review", "department_keys": ["marketing_growth"]},
        root=SKILLS_ROOT,
        registry={"schema_version": "empire.skill_trust.v1", "approved_skills": {}},
    )
    assert result["skills"] == []
    assert result["rejected"][0]["reason"] == "skill_not_approved"


def test_digest_mutation_fails_closed(tmp_path: Path):
    data = BODY.read_bytes()
    test_skill_dir = tmp_path / NAME
    test_skill_dir.mkdir()
    (test_skill_dir / "SKILL.md").write_bytes(data + b"\nunauthorised edit\n")
    with pytest.raises(SkillTrustError, match="skill_digest_mismatch"):
        load_pinned_skill(NAME, root=tmp_path, registry=_simulated_registry(data))


def test_promotion_still_requires_independent_review(tmp_path: Path):
    reg = tmp_path / "trust.json"
    reg.write_text('{"schema_version":"empire.skill_trust.v1","approved_skills":{}}')
    result = promotion_preflight(NAME, root=SKILLS_ROOT, trust_registry=reg)
    assert result["promoted"] is False
    assert result["founder_approval_recorded"] is False
    assert result["status"] == "BLOCKED"
    assert "independently_labelled_holdout_not_supplied" in result["blocks"]
