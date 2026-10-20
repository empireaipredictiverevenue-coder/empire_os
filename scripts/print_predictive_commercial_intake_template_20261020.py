"""Print an unfilled multi-industry commercial intake skeleton.

stdout is a plain JSON *draft template* suitable for redirection to an
operator-owned local file. Nothing is saved here, and no tenant, geography,
industry, deal, customer identity or lead quantity is assumed.
"""
from __future__ import annotations

import argparse
import json
from empire_os.predictive_commercial_requirements import INPUT_FIELDS

SCHEMA="empire.predictive_revenue.commercial_requirement_intake_template.v1"

def commercial_intake_template()->dict:
    values={name:None for name in INPUT_FIELDS}
    values.update(
        zip_codes=[],service_types=[],exclusions=[],accepted_event_types=[],
        exclusivity="unconfirmed",
    )
    if set(values)!=INPUT_FIELDS:
        raise AssertionError("template drift: existing commercial contract changed")
    return dict(sorted(values.items()))

def main()->int:
    parser=argparse.ArgumentParser(
        description="Print an UNFILLED commercial JSON draft. Redirect to a file and edit it."
    )
    parser.add_argument("--read-only",action="store_true",required=True)
    args=parser.parse_args()
    print(json.dumps(commercial_intake_template(),indent=2,sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
