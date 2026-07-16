# Lead Sniper Rules

Human-editable scoring + targeting config. The sniper agent reads this file
at startup (no LLM / Ollama needed). Edit, save, restart the agent to apply.

## Niches to hunt
roofing, hvac, plumbing, electrical, pest_control, landscaping, solar

## Urgency keywords (intent signal — "buying now")
need a, need an, need someone, looking for, emergency, urgent, asap, today,
right now, this weekend, tomorrow, quickly, fast, recommend, who do you use,
who do you recommend, any good, anyone know, hire, hiring, broken, leaking,
flooding, no heat, no ac, fire damage, storm damage, hail damage

## Scoring weights
w_intent: 0.5
w_fit: 0.3
w_recency: 0.2

## Thresholds
sniper_threshold: 0.6   # below this = skip (don't queue)
kill_threshold: 0.8     # above this = operator KILL alert

## Guard rails
max_per_cycle: 5        # max reviews queued per scan cycle
dedup_hours: 24         # skip if same source URL seen within this window

## Data sources
reddit_urgent: on
county_permits_urgent: on

## Review routing
mode: review_only       # finds go to empire_tasks (task_type=sniper_review)
                         # NEVER auto-email. Operator promotes + approves.
