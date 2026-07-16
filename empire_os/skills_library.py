"""
Empire OS Skills Library — agent-facing loader for the anthropics/skills
repo (now at /root/empire_os/skills_library/).

Each agent role maps to a set of relevant skills via ROLE_SKILLS.
`load_skills_for_role(role)` returns the full text of each relevant
SKILL.md, ready to inject into the agent's LLM context.

The library lives at /root/empire_os/skills_library/ (moved from
/tmp/repo_skills — was a /tmp hack, now a first-class repo under the
Empire OS package tree, per blueprint v4 pending item #3).
"""
from __future__ import annotations
import os
import re
from pathlib import Path
from typing import Optional

SKILLS_ROOT = Path(__file__).resolve().parent / "skills_library" / "skills"

# Map agent role -> list of relevant skill names. Add new roles here.
ROLE_SKILLS = {
    "data_analysis":   ["xlsx"],
    "markets_analysis": ["internal-comms"],
    "lead_handler":     [],
    "video_editing":    ["canvas-design", "web-artifacts-builder",
                        "frontend-design", "algorithmic-art"],
    "lead_sniper":      ["internal-comms"],
    "engineering":      ["mcp-builder", "claude-api", "webapp-testing"],
    "marketing":        ["brand-guidelines", "internal-comms",
                        "canvas-design", "theme-factory"],
    "design":           ["brand-guidelines", "canvas-design",
                        "frontend-design", "theme-factory",
                        "algorithmic-art"],
    "sales":            ["internal-comms", "pptx", "docx"],
    "copywriting":      ["brand-guidelines", "doc-coauthoring"],
    "email":            ["internal-comms", "docx"],
    "finance":          ["xlsx", "pdf"],
    "legal_compliance": ["docx", "pdf", "doc-coauthoring"],
    "innovator":        ["skill-creator", "algorithmic-art"],
    "council":          ["doc-coauthoring", "skill-creator"],
    "supervisor":       ["webapp-testing"],
    "os_upgrade":       ["webapp-testing"],
    "agi_scout":        ["webapp-testing"],
    "agi_marketing":    ["brand-guidelines", "internal-comms"],
    "agi_sales":        ["internal-comms", "pptx"],
    "commander":        ["internal-comms"],
    "default":          ["internal-comms"],
}


def _strip_frontmatter(text: str) -> str:
    """Strip YAML frontmatter from a markdown file."""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end > 0:
            return text[end + 4:].lstrip("\n")
    return text


def _read_skill(name: str, max_chars: int = 4000) -> Optional[str]:
    """Read a single SKILL.md by name, stripped of frontmatter, capped."""
    skill_md = SKILLS_ROOT / name / "SKILL.md"
    if not skill_md.exists():
        return None
    try:
        text = skill_md.read_text()
        body = _strip_frontmatter(text)
        if len(body) > max_chars:
            body = body[:max_chars] + f"\n\n... [truncated at {max_chars} chars]"
        return body
    except Exception as e:
        return f"[error reading {skill_md}: {e}]"


def load_skills_for_role(role: str,
                        max_chars_per_skill: int = 4000) -> list[dict]:
    """Return list of {name, body} dicts for skills relevant to role.

    Falls back to ['default'] if role not mapped. Returns [] if a
    skill name is mapped but the file is missing (so an outdated
    mapping doesn't break the agent).
    """
    skill_names = ROLE_SKILLS.get(role, ROLE_SKILLS["default"])
    out = []
    for name in skill_names:
        body = _read_skill(name, max_chars=max_chars_per_skill)
        if body:
            out.append({"name": name, "body": body})
    return out


def skills_context_for_role(role: str) -> str:
    """Format the skills as one LLM-ready string for `system` prompt."""
    skills = load_skills_for_role(role)
    if not skills:
        return ""
    parts = ["## RELEVANT SKILLS (from empire_os/skills_library)\n",
             "You have these skills loaded. Use them when relevant.\n"]
    for s in skills:
        parts.append(f"\n### {s['name']}\n{s['body']}\n")
    return "\n".join(parts)


def available_skills() -> list[str]:
    """List all skill names currently in the library."""
    if not SKILLS_ROOT.exists():
        return []
    return sorted([d.name for d in SKILLS_ROOT.iterdir()
                   if d.is_dir() and (d / "SKILL.md").exists()])


if __name__ == "__main__":
    print(f"Skills library root: {SKILLS_ROOT}")
    print(f"Available skills ({len(available_skills())}):")
    for s in available_skills():
        print(f"  - {s}")
    print()
    print("Sample: skills for 'video_editing':")
    for s in load_skills_for_role("video_editing", max_chars_per_skill=200):
        print(f"  - {s['name']}: {s['body'][:120]}...")
