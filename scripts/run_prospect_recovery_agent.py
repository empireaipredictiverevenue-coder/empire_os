"""Launch the single EmpireOS Prospect Recovery Agent."""
import argparse
import json
from pathlib import Path
from empire_os.prospect_recovery_agent import run_agent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    data = run_agent(Path(args.repo_root), execute=args.execute)
    print(json.dumps({
        "agent_id": data["agent_id"],
        "mode": data["mode"],
        "metrics": data["metrics"],
        "buyer_worklist_count": data["worklist_count"],
        "unit_requests": data["unit_requests"],
        "execution_mode": data["execution_mode"],
        "outbound_sent": False,
        "payments_changed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
