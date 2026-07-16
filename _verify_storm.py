import importlib
import json

ld = importlib.import_module("empire_os.agents.lead_deliverer_agent")

# 1) dry run count
n = ld.deliver_storm_leads(dry_run=True)
print("DRYRUN leads processed:", n)

# 2) inspect disaster matching + premium math for a few leads
mode, niches, mult = ld._read_disaster_env()
print("disaster mode:", mode, "niches:", niches, "multiplier:", mult)

buyers = ld.find_storm_buyers()
print("matched buyers:", [(b["tenant_id"], b["niche"], b["base_payout"], b["fee_rate"]) for b in buyers])

# show a couple of dryrun log lines
import subprocess
out = subprocess.run(["tail", "-4", "/root/feedback/lead_deliveries.jsonl"],
                     capture_output=True, text=True).stdout
for line in out.strip().splitlines():
    try:
        print(json.dumps(json.loads(line), indent=0)[:300])
    except Exception:
        print(line[:200])
