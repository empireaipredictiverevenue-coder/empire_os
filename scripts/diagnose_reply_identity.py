#!/usr/bin/env python3
"""Read-only redacted identity diagnosis; no outbound or DB writes."""
import json
from pathlib import Path
from empire_os.reply_identity_health import diagnose_reply_identity

SOURCE = Path('/srv/empire_os/runtime/conversations_replies_control/latest.json')

def main() -> int:
    try:
        report = diagnose_reply_identity(json.loads(SOURCE.read_text()))
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({'mode': 'OBSERVE', 'identity_ready': False,
                          'reason': 'reply_identity_snapshot_unavailable',
                          'error_type': type(exc).__name__, 'write_authorized': False}))
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0 if report['identity_ready'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
