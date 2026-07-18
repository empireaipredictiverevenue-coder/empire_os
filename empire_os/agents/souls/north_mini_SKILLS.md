# North-mini — Skill Spec

Used by `north_mini_agent.py` when producing each plan type. Output is strict
JSON (one of the shapes below). Never markdown inside values.

## Output shapes

```json
{"type":"growth_plan","horizon_days":90,
 "thesis":"...","plays":[{"name":"...","why":"...","steps":["..."],"kpi":"..."}],
 "next_3":["...","...","..."]}

{"type":"product_design","product":"...","problem":"...","users":"...",
 "features":["..."],"spec_path":"g-brain/build/specs/<name>.md","mvp_steps":["..."]}

{"type":"management","decision":"...","rationale":"...","owner":"...","deadline":"..."}

{"type":"agi_intel","signal":"...","source":"...","gap":"...","opp_for_empire":"...",
 "next_actions":["...","...","..."]}

{"type":"projection","projected_mrr_usd":0,"confidence_0_1":0.0,
 "top_leak":"...","next_actions":["...","...","..."]}
```

## Rules

- Base every field on the REAL state JSON you were given. No invented numbers.
- `projection.projected_mrr_usd` = estimated monthly recurring revenue from
  current leads × conversion assumption (state the assumption).
- `growth_plan.next_3` = the 3 highest-leverage moves this week.
- `product_design.spec_path` MUST be under `g-brain/build/specs/`.
- `management.owner` = a real role (Operations Manager, Founder, etc.).
- Max 5 items in any list.
- If state signals missing, output `{"type":"...","note":"insufficient data"}`.
- Never include secrets (auto-redacted anyway).
