#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from empire_os.lead_smart_launch_readiness import (
    build_launch_readiness,
)
from empire_os.buyer_supply_policy import lead_smart_confirmed_roofing_policy
from empire_os.lead_smart_site_handoff import verified_site_handoff_control


TRACKING = Path(
    "runtime/revenue/lead_smart/"
    "ringba/tracking_verification/latest.json"
)

ZIP_GATE = Path(
    "runtime/revenue/lead_smart/"
    "coverage/activation/latest.json"
)

ROUTING = Path(
    "runtime/revenue/lead_smart/"
    "ringba/routing_observation/latest.json"
)

OUT = Path(
    "runtime/revenue/lead_smart/"
    "launch_readiness/latest.json"
)


def load(path: Path) -> dict:
    if not path.exists():
        raise RuntimeError(
            f"missing evidence: {path}"
        )

    return json.loads(
        path.read_text()
    )


def approved_candidate_matches(report: dict, root: Path = Path(".")) -> bool:
    """Buyer approval is bound to both frozen source copies, never a new page."""
    expected = report.get("reviewed_source_sha256")
    if (report.get("approved") is not True
            or report.get("source_ref") != "gmail:1a12bc009d04fcc9"
            or not isinstance(expected, str) or len(expected) != 64):
        return False
    try:
        paths = (root / "templates/lead_smart/roofing/page.tsx",
                 root / "apps/empire-public-site/src/app/roofing/page.tsx")
        return all(not p.is_symlink() and hashlib.sha256(p.read_bytes()).hexdigest() == expected
                   for p in paths)
    except OSError:
        return False




# Built, source-matched and exposed at the actual edge after Seth's approval
# on 12 October; changing the HTML bytes cancels this particular release.
APPROVED_ROOFING_HTML_SHA256 = (
    "3b79c7856d2a9135900d797631693c75277947a78af47d10e1b9d6d4dff47997"
)


def approved_live_publication(
    report: dict, *, repo_root: Path, site_root: Path | None = None,
) -> bool:
    """Evidence that the exact approved roofing page is published, not call-ready."""
    site_root = site_root or Path("/srv/empire_os/apps/empire-public-site/out")
    if not approved_candidate_matches(report, root=repo_root):
        return False
    published = site_root / "roofing.html"
    try:
        if published.is_symlink():
            return False
        return hashlib.sha256(published.read_bytes()).hexdigest() == APPROVED_ROOFING_HTML_SHA256
    except OSError:
        return False

def effective_legal_release_verified() -> bool:
    """Reuse gateway admission for both deployed legal exports; never mint a receipt."""
    from empire_os.public_gateway import _approved_static_content_path

    return all(_approved_static_content_path(route) is not None
               for route in ("privacy", "terms"))


def founder_launch_approved(root: Path | None = None) -> bool:
    """Consume the recorded founder launch decision, not an invented approval."""
    root = root or Path(__file__).resolve().parents[1]
    path = root / "docs/evidence/lead_smart_founder_launch_intent_20261011.json"
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        scope = record.get("scope") or {}
        return (
            record.get("schema_version")
            == "empire.lead_smart.founder_launch_intent_record.v1"
            and record.get("decision")
            == "FOUNDER_APPROVES_EXISTING_LEAD_SMART_ROOFING_LAUNCH_SCOPE"
            and record.get("founder_instruction") == "go and i approve launch"
            and scope.get("campaign") == "CA8278ed3f26e9495b881fe3833174d007"
            and scope.get("route") == "existing Direct"
            and scope.get("acquisition") == "Empire-owned first-party organic/SEO only"
        )
    except (OSError, TypeError, ValueError, AttributeError):
        return False


def compute_live_launch_readiness(
    *, evidence_root: Path | None = None,
    repo_root: Path | None = None,
    now: datetime | None = None,
) -> dict:
    """Read real upstream snapshots and recompute Chicago clock on each request.

    No writes, provider requests or inferred authority. All original release
    gates including legal, routing, ANI and stop remain mandatory. Never trusts
    the timestamp of the older materialized launch_readiness/latest.json.
    """
    evidence_root = evidence_root or Path("/srv/empire_os/runtime/revenue/lead_smart")
    repo_root = repo_root or Path(__file__).resolve().parents[1]
    policy = lead_smart_confirmed_roofing_policy(
        source_ref="gmail:1a10c6b2530f2951"
    )
    direct = policy["routing"]["direct_route_requirements"]
    return build_launch_readiness(
        tracking=load(evidence_root / 'ringba/tracking_verification/latest.json'),
        zip_gate=load(evidence_root / 'coverage/activation/latest.json'),
        routing=load(evidence_root / 'ringba/routing_observation/latest.json'),

        operating_hours=policy["operating_hours"],

        # Verified source: Lead Smart Support Agent 9 October 2026.
        timezone_confirmation=policy["operating_hours_confirmation"],

        # Pass-through is contractually required on Direct, but evidence
        # of the runtime caller-ANI path has not been independently proved.
        caller_id_pass_through_verified=(
            direct["caller_id_pass_through_verified"] is True
        ),

        buyer_landing_page_approved=approved_candidate_matches(
            policy["routing"]["landing_review_report"], root=repo_root
        ),

        legal_release_verified=effective_legal_release_verified(),

        # The approved source is already published in production. This proof
        # is independently checked against the frozen exported HTML digest.
        # It does NOT grant calls while legal/provider/stop gates are held.
        landing_publication_authorized=(
            founder_launch_approved(root=repo_root)
            and approved_live_publication(
                policy["routing"]["landing_review_report"], repo_root=repo_root,
            )
        ),

        founder_live_traffic_authorized=
            founder_launch_approved(root=repo_root),

        # Actual wired, atomic site-handoff control; absent receipt holds.
        pilot_stop_verified=
            verified_site_handoff_control(),
        **({"now": now} if now is not None else {}),
    )


def main() -> int:
    result = compute_live_launch_readiness(
        evidence_root=Path('runtime/revenue/lead_smart'), repo_root=Path('.'),
    )
    OUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = (
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    tmp = OUT.with_suffix(
        ".tmp"
    )

    tmp.write_text(payload)
    tmp.replace(OUT)

    print(payload, end="")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
