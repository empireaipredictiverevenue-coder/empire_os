#!/usr/bin/env python3
"""Record OBSERVE agency plans without running the department work queue."""
import argparse
import json
from empire_os.marketing_agency import record_marketing_agency


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', default='/srv/empire_os')
    args = parser.parse_args()
    result = record_marketing_agency(args.repo_root)
    print(json.dumps({key: result[key] for key in (
        'department_key', 'agency_job_count', 'active_campaign_plan_count',
        'zero_cash_action_count', 'predictive_revenue_available_count',
        'predictive_revenue_unavailable_count')}, indent=2))


if __name__ == '__main__':
    main()
