#!/usr/bin/env python3
"""Read-only hook coverage report for existing Control Fabric; no side effects."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from empire_os.cross_department_hook_review import review_hook_coverage


if __name__ == "__main__":
    print(json.dumps(review_hook_coverage(), sort_keys=True, indent=2))
