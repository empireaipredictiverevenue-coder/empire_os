#!/usr/bin/env python3
"""Empire OS service manifest snapshot (LONG architect fix: IaC baseline).

Captures every empire* unit's state + key fields into JSON so future drift
is detectable (no more hand-edited systemd with no source of truth).
Run by self-heal? No - run on demand / weekly. Comparison tool = diff_manifest.py.
"""
import json
import subprocess
import os
from datetime import datetime, timezone

OUT = "/root/empire_os/feedback/services_manifest.json"


def run(cmd):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30).stdout
    except Exception as e:
        return f"ERR {e}"


def main():
    units = []
    raw = run('systemctl list-units "empire*" --all --no-legend --no-pager')
    for line in raw.splitlines():
        p = line.split()
        if not p:
            continue
        name = p[0]
        state = p[3] if len(p) > 3 else "?"
        sub = p[4] if len(p) > 4 else "?"
        # pull ExecStart + Type from file if present
        exe, typ = "", ""
        sf = f"/etc/systemd/system/{name}"
        try:
            with open(sf) as f:
                txt = f.read()
            for l in txt.splitlines():
                if l.strip().startswith("ExecStart="):
                    exe = l.strip()[10:]
                elif l.strip().startswith("Type="):
                    typ = l.strip()[5:]
        except OSError:
            pass
        units.append({"name": name, "load": p[1] if len(p) > 1 else "?",
                       "active": state, "sub": sub, "type": typ, "exec": exe})
    manifest = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "unit_count": len(units),
        "units": sorted(units, key=lambda u: u["name"]),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(manifest, f, indent=2)
    failed = [u["name"] for u in units if u["active"] == "failed"]
    print(f"manifest: {len(units)} units, {len(failed)} failed -> {OUT}")
    if failed:
        print("FAILED:", ", ".join(failed))


if __name__ == "__main__":
    main()
