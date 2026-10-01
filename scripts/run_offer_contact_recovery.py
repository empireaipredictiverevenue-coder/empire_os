#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from empire_os.search_fabric.site_probe import (
    probe_site,
)


ROOT = Path("/srv/empire_os")

QUEUE = (
    ROOT
    / "runtime/predictive_revenue"
    / "commercial_offer_book"
    / "contact_recovery_queue.json"
)

OUTPUT = (
    ROOT
    / "runtime/predictive_revenue"
    / "commercial_offer_book"
    / "contact_recovery_observed.json"
)


EMAIL_RE = re.compile(
    r"^[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+"
    r"@[A-Z0-9-]+(?:\.[A-Z0-9-]+)+$",
    re.I,
)


def clean(value: Any) -> str:
    return " ".join(
        str(value or "").strip().split()
    )


def clean_domain(value: Any) -> str:
    text = clean(value).lower()

    if not text:
        return ""

    if "://" not in text:
        text = "https://" + text

    host = urlsplit(text).hostname or ""

    return host.removeprefix("www.")


def syntactic_email(value: Any) -> str:
    email = clean(value).lower()

    if not EMAIL_RE.fullmatch(email):
        return ""

    local, domain = email.rsplit("@", 1)

    if not local or not domain:
        return ""

    # Reject common page-text concatenation artefacts.
    if domain.endswith((
        ".comcall",
        ".comemail",
        ".comcontact",
        ".netcall",
        ".orgcall",
    )):
        return ""

    return email


def probe_target(target: dict[str, Any]) -> dict[str, Any]:
    domain = clean_domain(
        target.get("domain")
    )

    result = {
        "company":
            target.get("company"),

        "domain":
            domain,

        "canonical_prospect_id":
            target.get(
                "canonical_prospect_id"
            ),

        "ready_product_codes":
            target.get(
                "ready_product_codes"
            ) or [],

        "products":
            target.get("products") or [],

        # A prior outbound/reference does NOT mean
        # a verified two-way conversation.
        "historical_context_reference_present":
            bool(
                target.get("conversation_refs")
            ),

        "person_bound_candidates": [],

        "generic_emails_observed": [],

        "probe_ok": False,

        "probe_error": None,

        "execution_authority": "none",

        "outreach_authorized": False,

        "database_write_performed": False,
    }

    if not domain:
        result["probe_error"] = "domain_missing"
        return result

    try:
        probe = probe_site(
            f"https://{domain}/",
            max_pages=6,
            request_timeout=6,
            time_budget_seconds=35,
            page_priority="people",
            public_only=True,
        )
    except Exception as exc:
        result["probe_error"] = (
            f"{type(exc).__name__}:"
            f"{str(exc)[:240]}"
        )
        return result

    result["probe_ok"] = (
        probe.get("ok") is True
    )

    result["pages_checked"] = len(
        probe.get("pages_checked") or []
    )

    generic = []

    for value in probe.get("emails") or []:
        email = syntactic_email(value)

        if email:
            generic.append(email)

    result["generic_emails_observed"] = list(
        dict.fromkeys(generic)
    )

    candidates = []

    for person in probe.get(
        "people"
    ) or []:
        if not isinstance(person, dict):
            continue

        name = clean(person.get("name"))
        title = clean(person.get("title"))

        email = syntactic_email(
            person.get("email")
        )

        source_url = clean(
            person.get("url")
            or person.get("evidence_url")
        )

        # Strict person-bound gate.
        if not name:
            continue

        if not email:
            continue

        if not source_url:
            continue

        candidates.append({
            "person_name": name,
            "person_title": title,

            "email": email,

            "source_url": source_url,

            "source":
                person.get("source")
                or "first_party_site",

            "source_kind":
                person.get("source_kind"),

            "person_explicitly_named":
                True,

            "email_directly_bound_to_person":
                True,

            # Still requires canonical MX/contact verifier.
            "email_verified":
                False,

            "promotion_ready":
                False,

            "verification_required": [
                "canonical_mx_email_verification",
                "current_suppression_check",
                "commercial_role_review",
            ],
        })

    deduped = {}

    for row in candidates:
        key = (
            row["person_name"].lower(),
            row["email"].lower(),
        )

        deduped[key] = row

    result[
        "person_bound_candidates"
    ] = list(deduped.values())

    return result


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--limit",
        type=int,
        default=15,
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=4,
    )

    args = parser.parse_args()

    if not QUEUE.exists():
        print("RECOVERY=BLOCKED")
        print("REASON=queue_missing")
        return 2

    queue = json.loads(
        QUEUE.read_text(
            encoding="utf-8"
        )
    )

    targets = [
        row
        for row in (
            queue.get("items") or []
        )
        if isinstance(row, dict)
    ]

    # Revenue-first deterministic grouping:
    # simpler, narrower permit product first,
    # then managed service, then capital.
    product_order = {
        "permit_intelligence": 0,
        "managed_service": 1,
        "private_capital_rollup": 2,
    }

    def order(row):
        codes = (
            row.get(
                "ready_product_codes"
            )
            or []
        )

        product_rank = min(
            (
                product_order.get(
                    str(code),
                    9,
                )
                for code in codes
            ),
            default=9,
        )

        return (
            product_rank,
            clean(
                row.get("company")
            ).lower(),
            clean(
                row.get("domain")
            ).lower(),
        )

    targets.sort(key=order)

    limit = max(
        1,
        min(args.limit, len(targets)),
    )

    targets = targets[:limit]

    workers = max(
        1,
        min(args.workers, 6),
    )

    rows = []

    with ThreadPoolExecutor(
        max_workers=workers
    ) as pool:

        futures = {
            pool.submit(
                probe_target,
                target,
            ): target
            for target in targets
        }

        for future in as_completed(
            futures
        ):
            try:
                rows.append(
                    future.result()
                )
            except Exception as exc:
                target = futures[future]

                rows.append({
                    "company":
                        target.get("company"),

                    "domain":
                        target.get("domain"),

                    "probe_ok":
                        False,

                    "probe_error":
                        (
                            f"{type(exc).__name__}:"
                            f"{str(exc)[:240]}"
                        ),

                    "person_bound_candidates":
                        [],

                    "execution_authority":
                        "none",

                    "outreach_authorized":
                        False,

                    "database_write_performed":
                        False,
                })

    rows.sort(
        key=lambda row: (
            0
            if row.get(
                "person_bound_candidates"
            )
            else 1,

            clean(
                row.get("company")
            ).lower(),
        )
    )

    bound_count = sum(
        len(
            row.get(
                "person_bound_candidates"
            )
            or []
        )
        for row in rows
    )

    targets_with_bound = sum(
        bool(
            row.get(
                "person_bound_candidates"
            )
        )
        for row in rows
    )

    payload = {
        "schema_version":
            "empire.predictive-revenue."
            "offer-contact-recovery.v1",

        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "target_count":
            len(rows),

        "probe_success_count":
            sum(
                row.get("probe_ok")
                is True
                for row in rows
            ),

        "targets_with_person_bound_email":
            targets_with_bound,

        "person_bound_candidate_count":
            bound_count,

        "execution_authority":
            "none",

        "outreach_authority":
            "none",

        "database_write_performed":
            False,

        "items":
            rows,
    }

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    tmp = OUTPUT.with_suffix(
        ".json.tmp"
    )

    tmp.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )

    tmp.replace(OUTPUT)

    print(
        "TARGETS_PROBED=",
        payload["target_count"],
    )

    print(
        "PROBE_SUCCESSES=",
        payload["probe_success_count"],
    )

    print(
        "TARGETS_WITH_PERSON_BOUND_EMAIL=",
        payload[
            "targets_with_person_bound_email"
        ],
    )

    print(
        "PERSON_BOUND_CANDIDATES=",
        payload[
            "person_bound_candidate_count"
        ],
    )

    print("OUTPUT=", OUTPUT)

    print()
    print(
        "=== PERSON-BOUND CONTACT CANDIDATES ==="
    )

    for row in rows:
        for person in (
            row.get(
                "person_bound_candidates"
            )
            or []
        ):
            print(
                row.get("company"),
                "|",
                row.get("domain"),
                "|",
                person.get("person_name"),
                "| title=",
                person.get("person_title"),
                "| email=",
                person.get("email"),
                "| source=",
                person.get("source_url"),
            )

    print()
    print(
        "=== NO PERSON-BOUND EMAIL YET ==="
    )

    for row in rows:
        if row.get(
            "person_bound_candidates"
        ):
            continue

        print(
            row.get("company"),
            "|",
            row.get("domain"),
            "| probe_ok=",
            row.get("probe_ok"),
            "| generic_email_count=",
            len(
                row.get(
                    "generic_emails_observed"
                )
                or []
            ),
            "| error=",
            row.get("probe_error"),
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
