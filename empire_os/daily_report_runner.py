#!/usr/bin/env python3
"""
Empire OS v3 — Daily Report Runner
===================================
Runs the daily report inside the empire-hub container (where DB has full schema)
and outputs to host feedback directory.
"""

import json
import subprocess
import sys
from pathlib import Path

FEEDBACK = Path("/root/feedback")
FEEDBACK.mkdir(parents=True, exist_ok=True)

def run_daily_report(args):
    """Run daily_report.py inside container and capture output."""
    cmd = [
        "incus", "exec", "empire-hub", "--",
        "bash", "-c",
        f"cd /root/empire_os && PYTHONPATH=/root/empire_os python3 -m empire_os.daily_report {' '.join(args)}"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    
    if result.returncode != 0:
        print(f"Container execution failed: {result.stderr}", file=sys.stderr)
        return result.returncode
    
    # Print stdout
    print(result.stdout)
    
    # If --save was requested, also save the JSON from container
    if "--save" in args or "--json" in args:
        # The container saves to /root/feedback/ inside container
        # Copy it to host
        date_str = subprocess.run(
            ["incus", "exec", "empire-hub", "--", "date", "+%Y-%m-%d"],
            capture_output=True, text=True, timeout=5
        ).stdout.strip()
        
        src = f"empire-hub/root/feedback/daily_report_{date_str}.json"
        dst = FEEDBACK / f"daily_report_{date_str}.json"
        
        cp_result = subprocess.run(
            ["incus", "file", "pull", src, str(dst)],
            capture_output=True, text=True, timeout=10
        )
        if cp_result.returncode == 0:
            print(f"\nSaved to host: {dst}")
        else:
            print(f"\nFailed to pull saved file: {cp_result.stderr}")
    
    return 0

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--json", action="store_true", help="Print JSON")
    p.add_argument("--save", action="store_true", help="Save to /root/feedback")
    p.add_argument("--send", default=None, help="Send to: telegram / telegram:-100... / etc")
    # Pass through unknown args to the container script
    args, unknown = p.parse_known_args()
    
    # Build args for container
    container_args = []
    if args.json:
        container_args.append("--json")
    if args.save:
        container_args.append("--save")
    if args.send:
        container_args.extend(["--send", args.send])
    container_args.extend(unknown)
    
    return run_daily_report(container_args)

if __name__ == "__main__":
    sys.exit(main())