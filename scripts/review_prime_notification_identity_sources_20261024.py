#!/usr/bin/env python3
"""Original PRIME source readiness: repository-only, non-executing review."""
import json
from empire_os.prime_original_notification_identity_source_audit import review_original_reminder_identity_source

def main():
    result=review_original_reminder_identity_source()
    print(json.dumps(result,sort_keys=True,indent=2))
    return 0 if result['execution_authority']=='none' and not result['verified_reminder_device_consent_authority'] else 1

if __name__=='__main__':
    raise SystemExit(main())
