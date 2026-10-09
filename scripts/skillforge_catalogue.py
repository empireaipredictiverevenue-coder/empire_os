#!/usr/bin/env python3
"""Print SkillForge inventory without mutating files or trust approvals."""
import json
from pathlib import Path
from empire_os.skillforge import catalogue

if __name__ == '__main__':
    print(json.dumps(catalogue(registry_path=Path('config/skill_trust_registry.json'), repo_root=Path.cwd()), indent=2, sort_keys=True))
