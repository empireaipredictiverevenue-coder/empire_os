#!/usr/bin/env python3
"""Review-only generation of evidence-checked SkillForge candidate versions."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from empire_os.skillforge_proposals import refresh_skill_proposals


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true', help='Save private review drafts; never approve skills')
    options = parser.parse_args()
    result = refresh_skill_proposals(Path.cwd(), apply=options.apply)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not result['invalid_observations'] and not result['inventory_truncated'] else 2

if __name__ == '__main__':
    raise SystemExit(main())
