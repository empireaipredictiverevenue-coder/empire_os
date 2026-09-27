#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from empire_os.trust_snapshot import build_trust_snapshot

ROOT = Path("/srv/empire_os")
OUTPUT = ROOT / "runtime" / "trust" / "latest.json"


def read(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def main() -> int:
    payload = build_trust_snapshot(
        ops_control=read(ROOT / "runtime/ops_control/latest.json"),
        security_audit=read(
            ROOT / "runtime/security/supabase_audit_latest.json"
        ),
        commercial_loop=read(ROOT / "runtime/commercial_loop/latest.json"),
    )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    tmp.replace(OUTPUT)
    print(json.dumps({
        "public_trust_center_ready": payload["assessment"][
            "public_trust_center_ready"
        ],
        "internal_score": payload["assessment"]["internal_score"],
        "evidence_coverage": payload["assessment"]["evidence_coverage"],
        "blockers": payload["assessment"]["blockers"],
        "security_findings": payload["security_findings"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
