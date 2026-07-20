# Superpowers + Claude Code — Survey for Empire OS

Cloned to:
- `/root/empire_os/superpowers/` (obra/superpowers, depth=1, ~14 skills + hooks + tests)
- `/root/empire_os/claude-code/` (anthropics/claude-code, depth=1, ~15 plugins + source)

## TL;DR

**superpowers** is pure behavior-shaping skill content — 14 markdown skills for the
"how an agent should work" layer (brainstorm → plan → execute → verify → review).
We already mirror several of these in our skill library; their canonical versions
are sharper and worth diffing against ours.

**claude-code** is the harness itself — useful as reference, but most of the value
for us is in the **plugins** directory (drop-in patterns for our own daemons) and
the **hook system** (which we can port to incus/systemd supervision).

Nothing here is a drop-in replacement. **Patterns and structure to copy, not code.**

---

## superpowers — what's useful

14 skill dirs under `skills/`. Quality bar: very high, red-flag tables, "iron laws,"
"if you skip this you're lying not verifying." Pairs well with our `caveman` voice
because their prose is terse and direct.

### Direct overlap with skills we already have → merge candidates

| Our skill | Their equivalent | Action |
|---|---|---|
| `verification-pattern` (ad-hoc) | `skills/verification-before-completion/` | Theirs is sharper. Has explicit "iron law" + 24-failure memory log. Adopt structure, keep our caveman voice. |
| `systematic-debugging` | `skills/systematic-debugging/` | Same 4-phase flow but theirs has Phase 4.5 ("3+ fixes failed → question architecture") which we don't have. **Adopt Phase 4.5 verbatim.** |
| `plan` | `skills/writing-plans/` + `executing-plans/` | Theirs is two-phase (write then execute). Ours is one. Split ours or add the `executing-plans` workflow as a follow-on skill. |
| `brainstorming` | `skills/brainstorming/` | Already have it. Theirs has `spec-document-reviewer-prompt.md` — reusable as a sub-agent template. |
| `test-driven-development` | `skills/test-driven-development/` | Same RED-GREEN-REFACTOR core, theirs has explicit `testing-anti-patterns.md`. Steal the anti-patterns list. |
| `dispatching-parallel-agents` | `skills/dispatching-parallel-agents/` | Already in our library (different version). Same dot-graph decision tree, different wording. Ours is fine. |

### New patterns worth adopting

- **`skills/subagent-driven-development/`** — full plan-execute loop with:
  - Fresh subagent per task (context isolation)
  - Implementer → task-reviewer (spec+quality) → fix-subagent cycle
  - Final broad code-review subagent at branch end
  - Has `implementer-prompt.md` and `task-reviewer-prompt.md` as templates we can
    adapt for our `agentic-resilience-patterns` skill. **Strongest find.**
- **`skills/using-superpowers/`** — bootstrap skill with `<EXTREMELY-IMPORTANT>`
  block. Pattern: `<SUBAGENT-STOP>` marker to disable in dispatched agents. We
  should add equivalent to our skills that get invoked from subagents.
- **`CLAUDE.md` / `AGENTS.md`** — symlink pattern (`AGENTS.md → CLAUDE.md`) for
  multi-tool support (works in claude/codex/cursor/kimi). Worth copying for our
  `empire_os/AGENTS.md` if we want our rules to load in any harness.
- **`writing-skills/anthropic-best-practices.md`** — meta-skill about authoring
  skills. Useful when we patch our own skills.
- **`dispatching-parallel-agents/`** + **`subagent-driven-development/`** together
  define a clean agent-coordination taxonomy we can mirror in Empire OS Guardian /
  Reasoning Loop architecture.

### Skip

- `brainstorming` (we have it)
- `dispatching-parallel-agents` (we have it, better version)
- `using-git-worktrees`, `finishing-a-development-branch` — dev-loop skills, not
  relevant to daemon-running Empire OS
- `writing-plans` (we have `plan`)
- `writing-skills/examples/` — too domain-specific (cursed language, etc.)

### Red flags we should steal verbatim

Their skills consistently include "Red Flags - STOP" tables and "Rationalization
Prevention" tables. Our skills sometimes have these, sometimes don't. Adding them
to every skill is the highest-leverage improvement available.

---

## claude-code — what's useful

This is the harness source. Most of it isn't directly portable to Empire OS
(FastAPI/SQLite/Python), but the **plugins** are platform-agnostic patterns.

### Plugins worth porting

| Plugin | What it does | Empire OS applicability |
|---|---|---|
| **`code-review/`** | 4 parallel agents (2x CLAUDE.md compliance + bug detector + git-blame analyzer) with confidence scoring (0-100, threshold 80) | **High.** Map directly to our `empire-os-qc` skill. Replace Claude reviewers with our personas (neural-scout, etc.). |
| **`security-guidance/`** | 3 layers: regex pattern warnings on Edit/Write, LLM diff review on Stop hook, agentic commit review | **High.** LLM diff-review pattern is exactly what we need in Guardian — review diffs before daemon rollout. 25-pattern list is a starter `secret_scan` ruleset. |
| **`hookify/`** | Markdown-with-frontmatter rules that turn into runtime hooks. No JSON editing. | **Medium.** Pattern is clean — `.claude/hookify.<name>.local.md` with regex + message. We could mirror this for Empire OS daemon policies instead of editing systemd unit files. |
| **`ralph-wiggum/`** | Stop-hook blocks exit, re-feeds same prompt → self-referential iteration loop | **Low.** Cool technique but our daemons are already continuous loops. Skip unless we add a "drive a persona to convergence" mode. |
| **`plugin-dev/`** | How to author a plugin (manifest, commands, agents, hooks, skills) | **Medium.** Use as reference if we ever ship our agents as installable plugins. |
| **`feature-dev/`** | Multi-agent code-writing workflow | **Low.** Closely tied to Claude Code's harness. Patterns noted, not copied. |

### Skim only

- `commit-commands/`, `pr-review-toolkit/` — git workflow, not our domain
- `explanatory-output-style/`, `learning-output-style/` — output style prefs
- `agent-sdk-dev/` — only relevant if we build on their SDK
- `frontend-design/` — UI design, not our domain
- `claude-opus-4-5-migration/` — model-specific, transient

### Useful infrastructure pieces

- **`hooks/`** in claude-code root — examples of PreToolUse, PostToolUse, Stop
  hooks. Our Hermes skill `skill_view` already supports hooks but we don't ship
  any. `claude-code/hooks/` is the best reference set.
- **`plugins/README.md`** — documents the plugin manifest schema (commands, agents,
  hooks, skills directories). Same shape we should use if we publish Empire OS
  personas as installable units.
- **`scripts/`** — TypeScript utilities for GitHub issue/PR lifecycle management.
  Some patterns (auto-close duplicates, sweep stale) are useful for any project
  doing high-volume triage; we could port to Python for our use.

---

## Concrete next steps for Empire OS

Ordered by leverage:

1. **Adopt Phase 4.5 from systematic-debugging** into our `systematic-debugging`
   skill. One paragraph. (15 min)
2. **Port the `code-review` plugin's confidence-scoring pattern** into
   `empire-os-qc` — 4 parallel reviewers, threshold 80, post only high-confidence.
   (Half-day)
3. **Port the `security-guidance` 25-pattern regex list** as initial seed for our
   secret/dangerous-call scanner. (Half-day)
4. **Steal `subagent-driven-development/implementer-prompt.md` template** for our
   `agentic-resilience-patterns` skill. (Hour)
5. **Add "Red Flags - STOP" + "Rationalization Prevention" tables** to all our
   skills that lack them. (Day)
6. **Port `hookify`'s markdown-with-frontmatter rule format** for daemon-level
   policy files. (Half-day, only if we keep adding policies)
7. **Add `<SUBAGENT-STOP>` equivalent to skills invoked from subagents** so they
   don't re-trigger. (Hour)

## What we explicitly do NOT adopt

- Superpowers' `AGENTS.md → CLAUDE.md` symlink (we don't run in multiple harnesses)
- Ralph Wiggum loop (overlaps with our daemon model)
- claude-code source code itself (harness-specific, irrelevant)
- Their contributor guidelines / PR template (we're not contributing upstream)

## Files referenced

- `/root/empire_os/superpowers/skills/verification-before-completion/SKILL.md`
- `/root/empire_os/superpowers/skills/systematic-debugging/SKILL.md`
- `/root/empire_os/superpowers/skills/dispatching-parallel-agents/SKILL.md`
- `/root/empire_os/superpowers/skills/subagent-driven-development/SKILL.md`
- `/root/empire_os/superpowers/skills/subagent-driven-development/implementer-prompt.md`
- `/root/empire_os/superpowers/skills/using-superpowers/SKILL.md`
- `/root/empire_os/claude-code/plugins/code-review/README.md`
- `/root/empire_os/claude-code/plugins/security-guidance/README.md`
- `/root/empire_os/claude-code/plugins/hookify/README.md`