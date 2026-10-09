#!/usr/bin/env python3
"""Print SkillForge inventory without mutating files or trust approvals."""
import json
from argparse import ArgumentParser
from pathlib import Path
from empire_os.skillforge import catalogue

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--okf-bundle', type=Path, default=None,
                        help='Optional private OKF research bundle (read-only)')
    args = parser.parse_args()
    print(json.dumps(catalogue(
        registry_path=Path('config/skill_trust_registry.json'),
        repo_root=Path.cwd(), okf_bundle_path=args.okf_bundle,
    ), indent=2, sort_keys=True))
