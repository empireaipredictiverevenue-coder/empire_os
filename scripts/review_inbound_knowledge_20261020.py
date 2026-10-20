"""Read-only review of an existing, operator-approved tenant knowledge version."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path

from empire_os.inbound_knowledge_store import OfflineKnowledgeRepository
from empire_os.inbound_tenant_knowledge import answer_from_knowledge


def main() -> None:
    p = argparse.ArgumentParser(description="Offline approved receptionist knowledge review")
    p.add_argument("--knowledge-db", type=Path, required=True)
    p.add_argument("--tenant-id", required=True)
    p.add_argument("--question")
    p.add_argument("--as-of")
    p.add_argument("--read-only", action="store_true", required=True)
    args = p.parse_args()

    with OfflineKnowledgeRepository(args.knowledge_db, read_only=True) as repo:
        pack = repo.get_active(args.tenant_id)
        if pack is None:
            result = repo.active_summary(args.tenant_id)
        elif not args.question:
            result = repo.active_summary(args.tenant_id)
        else:
            if not args.as_of:
                p.error("--as-of is required when reviewing a question")
            try:
                as_of = datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
                result = asdict(answer_from_knowledge(pack, args.question, as_of=as_of))
            except (ValueError, TypeError) as exc:
                p.error(f"invalid knowledge review: {exc}")
            result["tenant_id"] = args.tenant_id
            result["mode"] = "offline_approved_source_review_only"
        print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
