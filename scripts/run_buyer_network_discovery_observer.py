from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from empire_os.buyer_review_holds import is_do_not_pursue_domain


ROOT = Path("/srv/empire_os")

PYTHON = ROOT / ".venv" / "bin" / "python"

PREVIEW = ROOT / "scripts" / "buyer_discovery_preview.py"

OUTPUT = (
    ROOT
    / "runtime"
    / "buyer_network_intelligence"
    / "discovery_latest.json"
)


SEARCHES = (
    {
        "vertical": "roofing",
        "query":
            "roofing pay per call buyers publisher program",
    },
    {
        "vertical": "roofing",
        "query":
            "roofing lead buyers become a publisher",
    },
    {
        "vertical": "hvac",
        "query":
            "HVAC pay per call buyers publisher program",
    },
    {
        "vertical": "hvac",
        "query":
            "HVAC lead buyers publishers",
    },
    {
        "vertical": "restoration",
        "query":
            "restoration pay per call buyers publisher program",
    },
    {
        "vertical": "restoration",
        "query":
            "water damage restoration lead buyers publishers",
    },
    {
        "vertical": "home_services",
        "query":
            "home services lead buyers publisher network",
    },
    {
        "vertical": "home_services",
        "query":
            "home services RTB ping post lead buyers",
    },
    {
        "vertical": "home_services",
        "query":
            "home services lead exchange publishers",
    },
    {
        "vertical": "home_services",
        "query":
            "pay per call network home services publishers",
    },
)


DOMAIN_RE = re.compile(
    r"(?:https?://)?(?:www\.)?"
    r"([a-z0-9][a-z0-9.-]+\.[a-z]{2,})",
    re.I,
)


IGNORE_DOMAINS = {
    "google.com",
    "bing.com",
    "duckduckgo.com",
    "facebook.com",
    "linkedin.com",
    "youtube.com",
    "x.com",
    "twitter.com",
    "reddit.com",
}


def now_iso() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def atomic_write(
    payload: dict[str, Any],
) -> None:

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    tmp = OUTPUT.with_suffix(
        ".tmp"
    )

    tmp.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    tmp.replace(OUTPUT)


def preview_help() -> str:

    env = os.environ.copy()

    env.update(
        {
            "EMPIRE_MODE": "OBSERVE",
            "EMPIRE_EXECUTION_AUTHORITY":
                "OBSERVE",

            "OUTBOUND_ENABLED": "0",
            "EMPIRE_OUTBOUND_ENABLED": "0",
            "LIVE_OUTBOUND": "0",
        }
    )

    result = subprocess.run(
        [
            str(PYTHON),
            str(PREVIEW),
            "--help",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
    )

    return (
        (result.stdout or "")
        + "\n"
        + (result.stderr or "")
    )


def available_flags(
    help_text: str,
) -> set[str]:

    return set(
        re.findall(
            r"--[a-zA-Z0-9][a-zA-Z0-9-]*",
            help_text,
        )
    )


def domains_from_text(
    text: str,
) -> set[str]:

    found: set[str] = set()

    for match in DOMAIN_RE.finditer(
        text or ""
    ):

        domain = (
            match.group(1)
            .lower()
            .rstrip(".")
        )

        if domain.startswith("www."):
            domain = domain[4:]

        if domain in IGNORE_DOMAINS or is_do_not_pursue_domain(domain):
            continue

        found.add(domain)

    return found


def build_command(
    *,
    flags: set[str],
    query: str,
    vertical: str,
) -> list[str] | None:

    cmd = [
        str(PYTHON),
        str(PREVIEW),
    ]

    query_bound = False

    for flag in (
        "--query",
        "--search-query",
        "--search",
    ):
        if flag in flags:
            cmd.extend(
                [flag, query]
            )
            query_bound = True
            break

    for flag in (
        "--vertical",
        "--niche",
        "--category",
    ):
        if flag in flags:
            cmd.extend(
                [flag, vertical]
            )
            break

    if "--limit" in flags:
        cmd.extend(
            ["--limit", "25"]
        )

    elif "--max-results" in flags:
        cmd.extend(
            ["--max-results", "25"]
        )

    if "--observe" in flags:
        cmd.append("--observe")

    if "--dry-run" in flags:
        cmd.append("--dry-run")

    if "--no-send" in flags:
        cmd.append("--no-send")

    if "--no-outbound" in flags:
        cmd.append("--no-outbound")

    if "--preview" in flags:
        cmd.append("--preview")

    if not query_bound:
        return None

    return cmd


def run_search(
    command: list[str],
) -> dict[str, Any]:

    env = os.environ.copy()

    env.update(
        {
            "EMPIRE_MODE": "OBSERVE",
            "EMPIRE_EXECUTION_AUTHORITY":
                "OBSERVE",

            "OUTBOUND_ENABLED": "0",
            "EMPIRE_OUTBOUND_ENABLED": "0",
            "LIVE_OUTBOUND": "0",
        }
    )

    result = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=90,
    )

    combined = (
        (result.stdout or "")
        + "\n"
        + (result.stderr or "")
    )

    return {
        "returncode":
            result.returncode,

        "domains":
            sorted(
                domains_from_text(
                    combined
                )
            ),

        "stdout_tail":
            (result.stdout or "")[-5000:],

        "stderr_tail":
            (result.stderr or "")[-3000:],
    }


def main() -> int:

    help_text = preview_help()

    flags = available_flags(
        help_text
    )

    runs = []

    all_domains: set[str] = set()

    executable = True

    for item in SEARCHES:

        command = build_command(
            flags=flags,
            query=item["query"],
            vertical=item["vertical"],
        )

        if command is None:
            executable = False

            runs.append(
                {
                    **item,

                    "status":
                        "SKIPPED_FAIL_CLOSED",

                    "reason":
                        "existing_preview_has_no_query_argument",
                }
            )

            continue

        result = run_search(
            command
        )

        all_domains.update(
            result["domains"]
        )

        runs.append(
            {
                **item,

                "status":
                    "PASS"
                    if result[
                        "returncode"
                    ] == 0
                    else "FAIL",

                "command":
                    command,

                **result,
            }
        )

    payload = {
        "schema_version":
            "buyer-network-discovery-v1",

        "generated_at":
            now_iso(),

        "authority":
            "OBSERVE",

        "source":
            "existing_buyer_discovery_preview",

        "preview_script":
            str(
                PREVIEW.relative_to(ROOT)
            ),

        "available_flags":
            sorted(flags),

        "search_executable":
            executable,

        "query_count":
            len(SEARCHES),

        "candidate_domain_count":
            len(all_domains),

        "candidate_domains":
            sorted(all_domains),

        "runs":
            runs,

        "governance": {
            "outbound_authority":
                False,

            "traffic_activation_authority":
                False,

            "commercial_terms_authority":
                False,

            "funds_authority":
                False,
        },
    }

    atomic_write(payload)

    print(
        json.dumps(
            {
                "status": "PASS",

                "authority":
                    payload["authority"],

                "source":
                    payload["source"],

                "search_executable":
                    executable,

                "candidate_domain_count":
                    len(all_domains),

                "output":
                    str(OUTPUT),
            },
            indent=2,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
