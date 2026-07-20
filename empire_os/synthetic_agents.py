"""
Synthetic AGI Layer — shared base for the new domain agents.

Each new agent (mesh, business, growth, engineering, scheduling) extends
`SyntheticAgent` and implements its own observe / reason / act / learn.

The learn() hook runs after every cycle and uses synthetic intelligence
to enrich the agent's prompt context for future decisions.

v2 upgrades (memory + role + anti-repetition + skills gallery):

  - **SOUL preamble**: every agent loads its souls/<role>_SOUL.md on
    init and prepends it to the LLM system prompt on every cycle. The
    agent always knows its identity, rules, and operating principles.

  - **Persistent memory**: every action+outcome is appended to
    /root/<role>/memory.jsonl. Last N entries (default 10) are
    injected into the LLM context on the next cycle, so the agent
    remembers what it did and what worked.

  - **Anti-repetition**: before generating a decision, the agent
    checks if the same action signature ran in the last K cycles
    (default 3) with a non-success outcome. If so, it skips that
    action — prevents infinite loops of "try same thing, fail,
    try again".

  - **Skills gallery**: successful patterns (action signature +
    positive outcome) get extracted to /root/<role>/skills.jsonl.
    The top-K skills are loaded into the LLM context so the agent
    leans on what it knows works.

All four mechanisms are base-class behavior — every SyntheticAgent
subclass gets them for free.
"""
import json
import time
import logging
import hashlib
from abc import abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from empire_os.agent_core import Agent, OllamaClient
from empire_os.synthetic_intelligence import (
    SyntheticIntelligence,
    SyntheticExample,
)

logger = logging.getLogger("synthetic_agents")

# Default memory settings — overridable per-agent via constructor
DEFAULT_MEMORY_LIMIT = 10          # last N entries fed into LLM context
DEFAULT_ANTI_REP_WINDOW = 3        # last K cycles checked for repetition
DEFAULT_SKILLS_LIMIT = 5           # top-K skills fed into LLM context


class SyntheticAgent(Agent):
    """Agent base with SOUL preamble + memory + anti-repetition +
    skills gallery + synthetic intelligence + self-heal + learning.
    """

    def __init__(
        self,
        name: str,
        llm: Optional[OllamaClient] = None,
        backend=None,
        role: str = "agent",
        llm_url: str = "http://10.218.156.211:11434",
        llm_model: str = "llama3.2:3b",
        disable_llm: bool = False,
        memory_limit: int = DEFAULT_MEMORY_LIMIT,
        anti_rep_window: int = DEFAULT_ANTI_REP_WINDOW,
        skills_limit: int = DEFAULT_SKILLS_LIMIT,
        **kwargs,
    ):
        # Rule-based mode: never connect to Ollama (dead host = wasted cycles + spam).
        if disable_llm or llm is False:
            llm = False
        elif llm is None:
            llm = OllamaClient(base_url=llm_url, model=llm_model, timeout=180)
        super().__init__(name=name, llm=llm, backend=backend, **kwargs)
        self.role = role
        self.syn = SyntheticIntelligence(llm=self.llm, n_synthetic=3) if self.llm else None

        log_path = Path(f"/root/{role}/{role}.log")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log_path = log_path

        # v2: memory + skills persistence
        self._memory_path = Path(f"/root/{role}/memory.jsonl")
        self._memory_path.parent.mkdir(parents=True, exist_ok=True)
        self._skills_path = Path(f"/root/{role}/skills.jsonl")
        self._memory_limit = memory_limit
        self._anti_rep_window = anti_rep_window
        self._skills_limit = skills_limit

        # v2: load SOUL preamble once (cached for lifetime)
        self._soul_preamble = self._load_soul()

        self._log(
            f"init: role={role} memory_limit={memory_limit} "
            f"anti_rep={anti_rep_window} skills_limit={skills_limit} "
            f"soul_chars={len(self._soul_preamble)}"
        )

    # ── v2: SOUL + memory + anti-rep + skills ────────────────────

    def _strip_frontmatter(self, md: str) -> str:
        """Drop YAML frontmatter (--- ... ---) from a SKILL.md so only the
        body reaches the LLM as a system prompt."""
        if md.startswith("---"):
            end = md.find("\n---", 3)
            if end != -1:
                return md[end + 4:].lstrip("\n")
        return md

    def _load_soul(self) -> str:
        """Load souls/<role>_SOUL.md once. Returns "" if not found.

        Search order (first hit wins):
          1. live souls/ (role + name)
          2. /root/{role}/  (legacy)
          3. skills repos on disk (EmpireHermes/skills, empire-os-templates-repo,
             OpenMontage) — a SKILL.md whose name maps to this role overrides the
             drifted local SOUL. Keeps agent prompts versioned in the OSS repos.
        """
        soul_paths = [
            Path(f"/root/empire_os/empire_os/agents/souls/{self.role}_SOUL.md"),
            Path(f"/root/empire_os/empire_os/agents/souls/{self.name}_SOUL.md"),
            Path(f"/root/{self.role}/{self.role}_SOUL.md"),
        ]
        for p in soul_paths:
            if p.exists():
                try:
                    text = p.read_text()
                    self._log(f"soul loaded from {p} ({len(text)} chars)")
                    return text
                except Exception as e:
                    logger.warning("could not load soul %s: %s", p, e)
        # skills-repo fallback: map role -> repo SKILL.md
        repo_roots = [
            "/root/EmpireHermes/skills",
            "/root/empire-os-templates-repo",
            "/root/OpenMontage/skills",
        ]
        role_key = (self.role or self.name or "").lower()
        for root in repo_roots:
            r = Path(root)
            if not r.exists():
                continue
            # direct match: <root>/.../<role>_SOUL.md or <role>/SKILL.md
            for cand in r.rglob(f"{role_key}_SOUL.md"):
                try:
                    return cand.read_text()
                except Exception:
                    pass
            for cand in r.rglob("SKILL.md"):
                if role_key in cand.parent.name.lower() or role_key in cand.parent.parent.name.lower():
                    try:
                        return _strip_frontmatter(cand.read_text())
                    except Exception:
                        pass
        return ""

    def soul_preamble(self) -> str:
        """Public accessor — agents can include this in their LLM
        system prompt to always know who they are."""
        return self._soul_preamble

    def _load_memory(self) -> list[dict]:
        """Last N memory entries (most recent first)."""
        if not self._memory_path.exists():
            return []
        try:
            lines = self._memory_path.read_text(errors="ignore").splitlines()
            entries = []
            for ln in reversed(lines[-self._memory_limit:]):
                try:
                    entries.append(json.loads(ln))
                except Exception:
                    continue
            return entries
        except Exception as e:
            logger.warning("memory load failed: %s", e)
            return []

    def _load_skills(self) -> list[dict]:
        """Last K successful skills (most recent first)."""
        if not self._skills_path.exists():
            return []
        try:
            lines = self._skills_path.read_text(errors="ignore").splitlines()
            entries = []
            for ln in reversed(lines[-self._skills_limit:]):
                try:
                    entries.append(json.loads(ln))
                except Exception:
                    continue
            return entries
        except Exception as e:
            logger.warning("skills load failed: %s", e)
            return []

    @staticmethod
    def _action_signature(action: str, decision: str) -> str:
        """Stable signature for an action — used by anti-repetition.

        Hashes action + first 200 chars of decision (enough to
        distinguish different actions; same decision = same sig)."""
        h = hashlib.sha256()
        h.update(action.encode("utf-8"))
        h.update(b"\x00")
        h.update((decision or "")[:200].encode("utf-8"))
        return h.hexdigest()[:16]

    def should_skip_action(self, action: str, decision: str) -> tuple[bool, str]:
        """Anti-repetition check. Returns (skip, reason).

        If the same action signature ran in the last K cycles with
        outcome != success, returns (True, reason). Otherwise False.
        """
        if self._anti_rep_window <= 0:
            return False, "anti-rep disabled"
        sig = self._action_signature(action, decision)
        memory = self._load_memory()
        recent = [m for m in memory[:self._anti_rep_window]
                  if m.get("sig") == sig]
        if not recent:
            return False, "no recent repeats"
        fails = [m for m in recent if not m.get("success")]
        if fails:
            return True, (f"action repeated {len(fails)}x in last "
                          f"{self._anti_rep_window} cycles without success")
        return False, "recent repeats succeeded"

    def _record_outcome(
        self, action: str, decision: str, result: dict, success: bool
    ):
        """Append a memory entry. Always called from tick()."""
        sig = self._action_signature(action, decision)
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "cycle": self.context.cycle,
            "role": self.role,
            "action": action,
            "sig": sig,
            "decision_preview": (decision or "")[:200],
            "result_summary": (
                result.get("summary", "") if isinstance(result, dict) else ""
            )[:200],
            "success": success,
        }
        try:
            with self._memory_path.open("a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.warning("memory write failed: %s", e)

        # If this was a success, also add to skills gallery
        if success:
            skill = {
                "ts": entry["ts"],
                "cycle": self.context.cycle,
                "action": action,
                "sig": sig,
                "decision_pattern": entry["decision_preview"],
                "outcome": entry["result_summary"],
            }
            try:
                with self._skills_path.open("a") as f:
                    f.write(json.dumps(skill) + "\n")
            except Exception as e:
                logger.warning("skills write failed: %s", e)

    def build_reason_context(self, state: dict) -> str:
        """Build the contextual preamble that agents inject into their
        LLM reason() prompt. Includes:
          - SOUL preamble (identity, rules, principles)
          - Recent memory (what we did last, what worked)
          - Skills gallery (top-K successful patterns)

        Returns a single string the subclass can append to its
        LLM `system` parameter.
        """
        chunks = []

        if self._soul_preamble:
            chunks.append("## YOUR IDENTITY & RULES (SOUL)\n"
                          + self._soul_preamble)

        memory = self._load_memory()
        if memory:
            mem_lines = [f"  - c{m['cycle']} [{m['action']}] "
                         f"{'OK' if m['success'] else 'FAIL'} "
                         f"{m['result_summary'][:120]}"
                         for m in memory[:self._memory_limit]]
            chunks.append("## YOUR RECENT ACTIVITY (memory)\n"
                          + "\n".join(mem_lines))

        skills = self._load_skills()
        if skills:
            sk_lines = [f"  - c{s['cycle']} [{s['action']}] "
                        f"{s['decision_pattern'][:120]}"
                        for s in skills[:self._skills_limit]]
            chunks.append("## WHAT WORKED (skills gallery)\n"
                          + "\n".join(sk_lines))

        return "\n\n".join(chunks) if chunks else ""

    def _success_from_result(self, result: dict) -> bool:
        """Heuristic — was this cycle successful? Subclasses can
        override for custom logic."""
        if not isinstance(result, dict):
            return False
        if result.get("error"):
            return False
        # Check for explicit failure indicators in summary or ok field
        if result.get("ok") is False:
            return False
        summary = (result.get("summary") or "").lower()
        # Any of these markers => failure
        for marker in ("error", "fail", "failed", "exception",
                       "traceback", "skipped_duplicate"):
            if marker in summary:
                return False
        return True

    # ── v1 unchanged: log + learn ────────────────────────────────

    def _log(self, msg: str, level: str = "INFO"):
        ts = datetime.now(timezone.utc).isoformat()
        line = "[%s] [%s] %s\n" % (ts, level, msg)
        with self._log_path.open("a") as f:
            f.write(line)
        logger.info(line.strip())

    def learn(self, state: dict, decision: str, result: dict) -> dict:
        """Generate synthetic training examples from this cycle's data."""
        try:
            decision_dict = {"raw": decision}
            try:
                decision_dict = json.loads(decision)
            except Exception:
                pass
            examples = self.syn.augment(state, decision_dict) if self.syn else []
            self._log("learn: %d synthetic examples generated" % len(examples))
            return {
                "examples": [
                    {"input": e.input, "expected_output": e.expected_output, "rationale": e.rationale}
                    for e in examples
                ]
            }
        except Exception as e:
            self._log("learn error: %s" % e, "ERROR")
            return {"examples": [], "error": str(e)}

    def tick(self) -> dict:
        """Observe → Reason (with SOUL+memory+skills) → Act (anti-rep) → Learn → Record."""
        self.context.cycle += 1
        t0 = time.time()
        try:
            state = self.observe()
            decision = self.reason(state)
            result = self.act(decision)

            # v2: extract action name from decision (best-effort)
            action_name = "unknown"
            try:
                d = json.loads(decision) if decision else {}
                if isinstance(d, dict):
                    action_name = d.get("action", "unknown")
            except Exception:
                pass

            # v2: anti-repetition — if this action has failed in the
            # last K cycles, mark the result as "skipped_duplicate"
            # so memory records the attempt.
            skip, skip_reason = self.should_skip_action(action_name, decision)
            if skip:
                self._log(f"anti-rep: {skip_reason}")
                result = {
                    **result,
                    "skipped_duplicate": True,
                    "skip_reason": skip_reason,
                    "summary": f"skipped: {skip_reason}",
                }

            learn_result = self.learn(state, decision, result)
            elapsed = time.time() - t0

            summary = result.get("summary", "") if isinstance(result, dict) else str(result)[:80]
            self._log(
                "cycle %d: %.1fs — %s" % (self.context.cycle, elapsed, summary)
            )

            # v2: record outcome to memory + skills gallery
            self._record_outcome(
                action=action_name,
                decision=decision or "",
                result=result,
                success=self._success_from_result(result),
            )

            self.context.last_result = {
                "cycle": self.context.cycle,
                "elapsed": round(elapsed, 2),
                "decision_preview": decision[:120] if decision else "",
                "result": result,
                "learning": learn_result,
                "skipped_duplicate": skip,
            }
            return self.context.last_result
        except Exception as e:
            self._log("tick error: %s" % e, "ERROR")
            return {"cycle": self.context.cycle, "error": str(e)}

    @abstractmethod
    def observe(self) -> dict:
        ...

    @abstractmethod
    def reason(self, state: dict) -> str:
        ...

    @abstractmethod
    def act(self, decision: str) -> dict:
        ...


def asdict(obj):
    """Backport of dataclasses.asdict for safety."""
    try:
        from dataclasses import asdict as _ad
        return _ad(obj)
    except Exception:
        return obj.__dict__ if hasattr(obj, "__dict__") else {}


# ── Quick-construct helpers for the new agents ─────────────────────

def build_agent(role: str, agent_class, **kwargs):
    """Build a new agent and register it with the registry."""
    from empire_os.agent_registry import register_agent

    container = "%s-agent" % role
    log_path = "/root/%s/%s.log" % (role, role)
    agent = agent_class(name=container, role=role, **kwargs)
    register_agent(
        name=container,
        role=role,
        log_path=log_path,
        health_url=kwargs.get("health_url"),
        description=kwargs.get("description", "%s agent" % role),
    )
    return agent