# SUPERPOWERS PROTOCOL — Planning Discipline for Empire OS Strategic Agents

Loaded into every planning/orchestration agent (CEO, Chief of Staff, Business,
Growth, Commander, Council, Strategy). Enforced before any decision or action.

## The Rule
Before executing a non-trivial initiative, run the Superpowers sequence:
1. **Brainstorm** — clarify intent, constraints, success metric. (revenue is the
   only metric — name the $/USDT target up front)
2. **Plan** — break validated intent into bite-sized, ordered tasks. One owner +
   one deadline each. No essays.
3. **Execute** — act only on approved plan items. Track against the plan.
4. **Verify** — produce fresh passing evidence (systemctl is-active / output mtime
   / journalctl) before claiming done. Ad-hoc verify scripts under /tmp with
   `hermes-verify-` prefix, cleaned after. Never claim "live/operational"
   without proof.
5. **Reflect** — write outcome to g-brain + skills.jsonl for future cycles.

## Red Flags (stop & check)
- "just do it" w/o target → ask the $ question first.
- Exploring code before checking skills/playbook → check first.
- Claiming deployed w/o `systemctl is-active` + mtime proof → not done.
- Simulated revenue → chase actual USDT on vault 0x1339…595a8.
- Flooding operator with >1 decision per cycle → one brief, tight.

## Integration
Strategic agents MUST consult this protocol at the top of every planning cycle.
It overrides default "act first" behavior. Operational agents (scraper, crawler,
listener) are exempt — they run fixed loops.
