#!/usr/bin/env python3
"""One-shot cross-surface SEO/AEO/GEO/A2A review. No writes or services."""
import argparse
import json
from empire_os.search_intelligence.four_surface_discovery import run

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-only", action="store_true", required=True)
    args = parser.parse_args()
    assert args.review_only
    print(json.dumps(run(), sort_keys=True, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
