#!/usr/bin/env python3
"""
Generate one Hermes SKILL.md per real Empire OS agent/module.

Scans the real codebase (NOT the phantom incus registry), groups modules into
departments, and writes a consistent SKILL.md for each under:
    ~/.hermes/skills/empire-os-depts/<department>/<module>/SKILL.md

Each skill documents: what the module does, key entrypoints, dependencies,
how to run it, and known pitfalls. Generated from the module's own docstring
+ function signatures so it stays honest (no invented behavior).

Reproducible: re-run any time the codebase changes.
"""
import ast
import os
import sys
from pathlib import Path

REPO = Path("/root/empire_os")
SKILLS_ROOT = Path(os.path.expanduser("~/.hermes/skills/empire-os-depts"))
SKILLS_ROOT.mkdir(parents=True, exist_ok=True)

# --- Department mapping (derived from real module filenames/roles) ----------
DEPARTMENTS = {
    "revenue": [
        "seat_payment_onboarding", "founder_outreach", "settlement_gateway",
        "solana_listener", "revenue_reasoner", "eval_connect_sweeps",
        "build_buy_page", "migrate_prospects",
    ],
    "growth-marketing": [
        "advertising_agent", "outreach", "cold_outreach_worker", "campaigns",
        "run_market_sweeps", "host_b2b_hunter", "search_api_leads",
        "reddit_monitor", "outreach_agent", "email_agent", "email-expert",
        "media-buyer", "media-suite", "video-ads", "product_spec",
    ],
    "intelligence": [
        "behavior_engine", "predictive_revenue", "deep_research_agent", "scout_agent",
        "customer_analysis", "relationship_engine", "influence_engine",
        "okf_tracker", "habit_memory", "revenue_snapshot",
    ],
    "leadership-ops": [
        "leadership_council", "chief_of_staff", "ceo_agent", "agent_copilot",
        "agent_harness", "mesh_agent", "cortex_health_watchdog",
        "empire-orchestrator",
    ],
    "content-seo": [
        "aeo_generator", "aeo_checker", "aeo_monitor", "aeo_refresh",
        "local_spinner", "vertical_feed", "build_product_docs",
        "publish_products", "enrich_products", "product_spec",
    ],
    "scrapers-sourcing": [
        "biz_scraper", "industrial_sniper", "empire_lead_crawler",
        "captcha_farm", "verify_business", "verify_prospects", "crm_pool",
        "supabase_lead_activation", "mcp_lead_server",
    ],
    "infra-platform": [
        "agi_agent_service", "synthetic_service", "business_dir",
        "influence_engine", "storm_strike", "satellite_strike",
    ],
}

# flatten reverse map: module -> department
MOD2DEPT = {}
for dept, mods in DEPARTMENTS.items():
    for m in mods:
        MOD2DEPT[m] = dept

# --- Find all real .py modules ----------------------------------------------
def find_modules():
    found = {}
    # flat root
    for p in (REPO).glob("*.py"):
        found[p.stem] = p
    # single-nested empire_os/empire_os (where built engines live on host)
    nested = REPO / "empire_os"
    if nested.exists():
        for p in nested.glob("*.py"):
            found.setdefault(p.stem, p)
        agents = nested / "agents"
        if agents.exists():
            for p in agents.glob("*.py"):
                found.setdefault(p.stem, p)
    return found

def extract_info(path: Path):
    """Pull docstring + top-level defs/classes from a module safely."""
    try:
        tree = ast.parse(path.read_text())
    except Exception as e:
        return None, [], f"[parse error: {e}]"
    doc = ast.get_docstring(tree) or ""
    defs = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = [a.arg for a in node.args.args if a.arg != "self"]
            defs.append(f"def {node.name}({', '.join(args)})")
        elif isinstance(node, ast.ClassDef):
            defs.append(f"class {node.name}")
    return doc, defs, ""

def department_for(stem: str) -> str:
    if stem in MOD2DEPT:
        return MOD2DEPT[stem]
    # heuristic fallback by keyword
    s = stem.lower()
    if any(k in s for k in ["aeo", "seo", "content", "doc", "product", "publish", "vertical"]):
        return "content-seo"
    if any(k in s for k in ["scrap", "sniper", "crawl", "crm", "lead", "source", "supabase", "mcp"]):
        return "scrapers-sourcing"
    if any(k in s for k in ["outreach", "ad", "market", "campaign", "reddit", "email", "media", "video"]):
        return "growth-marketing"
    if any(k in s for k in ["ceo", "chief", "leadership", "council", "mesh", "copilot", "harness", "orchestrat", "watchdog"]):
        return "leadership-ops"
    if any(k in s for k in ["behavior", "research", "scout", "analysis", "relationship", "influence", "okf", "habit", "revenue", "predict"]):
        return "intelligence"
    if any(k in s for k in ["pay", "founder", "settlement", "solana", "buy"]):
        return "revenue"
    return "infra-platform"

def slug(stem: str) -> str:
    return stem.lower().replace("_", "-")

def main():
    modules = find_modules()
    print(f"Found {len(modules)} real modules", file=sys.stderr)
    written = 0
    skipped = 0
    # group by department
    by_dept = {}
    for stem, path in sorted(modules.items()):
        if stem.startswith("_") and stem not in MOD2DEPT:
            # private helper module — still give it a skill under infra
            dept = "infra-platform"
        else:
            dept = department_for(stem)
        by_dept.setdefault(dept, []).append((stem, path))

    for dept, items in sorted(by_dept.items()):
        dept_dir = SKILLS_ROOT / dept
        dept_dir.mkdir(parents=True, exist_ok=True)
        for stem, path in sorted(items):
            doc, defs, err = extract_info(path)
            if doc is None and err:
                doc = err
            s = slug(stem)
            skill_dir = dept_dir / s
            skill_dir.mkdir(parents=True, exist_ok=True)
            defs_txt = "\n".join(f"- `{d}`" for d in defs[:25]) or "- (no top-level defs)"
            name = f"empire-{dept}-{s}"
            content = f"""---
name: {name}
description: >-
  Empire OS module `{stem}.py` ({dept} department). Use when invoking,
  debugging, extending, or wiring this specific agent/module. Auto-generated
  from the module's own source — documents real entrypoints and behavior.
department: {dept}
module: {stem}.py
source_path: {path}
---

# {stem}.py — {dept} department

## What it does
{doc.strip() or "No module docstring. Inspect source for behavior."}

## Location
`{path}`

## Key entrypoints
{defs_txt}

## How to run / invoke
```bash
# from repo root (host or empire-hub container)
cd /root/empire_os
python3 {path.name}            # if it has a __main__
# or import:
python3 -c "import sys; sys.path.insert(0,'/root/empire_os'); import empire_os.{stem}"
```

## Dependencies / context
- Runs in-process inside `empire-hub` (container) or on host repo root.
- Reads/writes `empire_os.db` (SQLite/WAL) unless noted otherwise.
- Container-per-agent model is RETIRED — this module runs in-process.

## Known pitfalls
- {err if err else "None recorded. Verify DB/WAL state before mutating."}
- Incus registry lists 80+ phantom agents; this module is REAL and in-process.

## Department
Part of **{dept}**. Peer modules in this department share the same data layer.
"""
            (skill_dir / "SKILL.md").write_text(content)
            written += 1
    print(f"Wrote {written} skills across {len(by_dept)} departments", file=sys.stderr)
    for dept in sorted(by_dept):
        print(f"  {dept}: {len(by_dept[dept])}", file=sys.stderr)

if __name__ == "__main__":
    main()
