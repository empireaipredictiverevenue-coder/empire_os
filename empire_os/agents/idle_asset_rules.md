# Idle-Asset / Waste / Logistics Sniper Rules

Human-editable config. Agent reads at startup (no LLM). Edit + restart.

## Scoring thresholds
kill_threshold: 0.8        # above this = operator KILL alert
max_per_cycle: 5           # max reviews queued per scan cycle
dedup_hours: 24            # skip if same url seen within window

## Opportunity types detected
- idle_truck: idle trucks, parked fleets, unused equipment
- waste_leakage: illegal dumping, spills, hazardous waste, leaks
- logistics_waste: empty/vacant warehouses, disused distribution,
  abandoned cold storage, idle industrial

## Data sources (public RSS, no API key)
- travis_county_permits
- austin_permits
- logistics_rss (freightwaves)

## Review routing
mode: review_only           # finds -> empire_tasks (task_type=idle_asset_review)
                            # NEVER auto-email. Operator promotes + approves.
