# Geometric Reasoning for Agents — Deep Research

How Empire OS agents reason about **workflows** and **builds** as geometric
structures (graphs of thoughts) instead of flat prompt chains.

---

## 1. Why geometry, not chains

Flat one-shot prompting:
- no backtracking (dead path = total failure)
- no parallelism (one worker, serial)
- no composition (can't merge partial solutions)

Engineering work is a **graph**: branches (approaches), merges (integration),
cycles (test→fix), and acyclicity constraints (no circular imports / deps).
Modeling it geometrically lets agents search, prune, and compose like humans.

## 2. Core engines

### Tree-of-Thoughts (ToT) — Yao et al. 2023 (arXiv:2305.10601)
- LLM generates **branches** of candidate steps
- a **judge** (LLM or verifier) scores each leaf
- search: BFS/DFS over the thought tree, **backtrack** on dead ends
- our use: `geometric.tot_plan()` searches change-set space, keeps top-k

### Graph-of-Thoughts (GoT) — Besta et al. 2023 (arXiv:2308.09687)
- thoughts are **nodes**; edges = dependency/aggregation/merge
- supports **aggregation** (reduce many nodes → one) and **merging**
- our use: `geometric.got_merge()` merges parallel worker diffs, resolves conflicts

### Reflexion — Shinn et al. 2023 (arXiv:2303.11366)
- agent reflects on failures, writes self-feedback to memory
- our use: verifier node writes fail reason → coder re-enters with context

### Plan-and-Solve / ReAct — Wei et al. / Yao et al.
- explicit plan step before act; interleave thought+action+observation
- our use: planner node = plan, coder/tester = act+observe

### DSPy — Khattab et al. (arXiv:2310.03714)
- programmatic prompts as composable modules; optimize the graph, not the text
- integration: replace hand-written prompts with dspy modules + teleprompter

### Neuro-symbolic (Z3 / OR-Tools)
- hard constraints on build graphs (import acyclicity, schema consistency)
- our use: verifier runs a constraint check before merge

## 3. Benchmarks to track

| Bench | Tests | Relevance |
|-------|-------|-----------|
| SWE-bench | real GitHub issue→PR | our coder/reviewer loop |
| HumanEval / MBPP | function-level code | unit of coder |
| GSM8K / MATH | multi-step reasoning | ToT gains here are large |
| ARC | abstract visual reasoning | pure geometric reasoning |
| Graph tasks (CLRS) | algorithm graphs | GoT / search |

Reported lifts: ToT on GSM8K ~70%→~90% (vs CoT); GoT on sorting ~+30% over ToT.

## 4. Our integration (shipped in /root/empire_os/factory)

```
planner  ── ToT search over change-sets ──> scored path + target files
coder    ── 2 parallel branches ──> GoT merge (conflict-resolved diff)
reviewer ── LLM bug/security judge
tester   ── ad-hoc verify gate (sys.exit 0)
verifier ── Reflexion loop (max 3 retries, backtrack to coder)
```
- context engine (repo_map / scope_files) = the **embedding of the graph**
- Incus sandbox = isolated node execution (no shared-state wedging)
- llm_gateway = single brain, multi-tier (reason/bulk)

## 5. Build-time geometric checks (next)

1. import-graph acyclicity (static scan before merge)
2. schema consistency (SQLite migration graph DAG)
3. dependency resolution via OR-Tools for parallel agent scheduling
4. RAG retrieval over code = node embedding lookup (Pinecone wired)

## 6. Open questions

- cost: ToT = k× LLM calls. cap branch/depth (we use 3×2).
- judge reliability: LLM self-score noisy → cross-check with symbolic verifier.
- when to escalate reason→bulk tier (gateway flake on reason tier observed).

---
Status: geometric.py + orchestrator wired. Verified compile + graph run.
Gateway `reason` tier flaky (Bai timeout) — bulk tier solid.
