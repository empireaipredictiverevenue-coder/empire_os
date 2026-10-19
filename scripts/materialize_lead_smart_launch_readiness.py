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
from empire_os.lead_smart_buyer_admin_proof import verified_buyer_admin_proof


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


# The reviewed roofing source remains preserved independently of the live page.
# e440dc1b changes ONLY the hero link, from a disabled placeholder to the
# existing ZIP/recording-consent workflow. It does not expose a phone number.
# Both the source variant and its built HTML are pinned: no arbitrary page
# change inherits Lead Smart's original review.
ROOFING_HERO_CTA_SOURCE_SHA256 = (
    "9cf8437f7cdc1312b43c9ad99248a9663a4c6c0be68b3a387c4f21d2b9a61641"
)
ROOFING_HERO_CTA_HTML_SHA256 = (
    "0e1efde0f12311cd0a722777b91b68ecb95313ef947c4a186a0c90b43a66cc22"
)


def _approved_source_variant(report: dict, root: Path) -> str | None:
    expected = report.get("reviewed_source_sha256")
    if (report.get("approved") is not True
            or report.get("source_ref") != "gmail:1a12bc009d04fcc9"
            or not isinstance(expected, str) or len(expected) != 64):
        return None
    reviewed = root / "templates/lead_smart/roofing/page.tsx"
    live = root / "apps/empire-public-site/src/app/roofing/page.tsx"
    try:
        if reviewed.is_symlink() or live.is_symlink():
            return None
        if hashlib.sha256(reviewed.read_bytes()).hexdigest() != expected:
            return None
        active = hashlib.sha256(live.read_bytes()).hexdigest()
        if active in (expected, ROOFING_HERO_CTA_SOURCE_SHA256):
            return active
    except OSError:
        return None
    return None


def approved_candidate_matches(report: dict, root: Path = Path(".")) -> bool:
    """Preserve original buyer review; admit only the pinned consent-link variant."""
    return _approved_source_variant(report, root) is not None



# Built, source-matched and exposed at the actual edge after Seth's approval
# on 12 October; changing the HTML bytes cancels this particular release.
# Reconciled 16 Oct after buyer message gmail:1a145b32d742f3b1
# specifically acknowledged the added on-page call recording notice. Both
# original approved TSX sources remain byte-for-byte at frozen buyer hash.
# The present HTTPS /roofing and generated out/roofing.html are identical
# sha256:db3521c904f20ab774aebec08d71d70d21fe8695adc9ec8c1626a8502be20aba.
# This exact-byte publication check does NOT satisfy independent routing,
# recording retention/consent, tracking, legal or supervised-stop gates.
APPROVED_ROOFING_HTML_SHA256 = (
    "db3521c904f20ab774aebec08d71d70d21fe8695adc9ec8c1626a8502be20aba"
)


def approved_live_publication(
    report: dict, *, repo_root: Path, site_root: Path | None = None,
) -> bool:
    """Evidence that the exact approved roofing page is published, not call-ready."""
    site_root = site_root or Path("/srv/empire_os/apps/empire-public-site/out")
    source_variant = _approved_source_variant(report, repo_root)
    if source_variant is None:
        return False
    published = site_root / "roofing.html"
    try:
        if published.is_symlink():
            return False
        expected_html = (
            ROOFING_HERO_CTA_HTML_SHA256
            if source_variant == ROOFING_HERO_CTA_SOURCE_SHA256
            else APPROVED_ROOFING_HTML_SHA256
        )
        return hashlib.sha256(published.read_bytes()).hexdigest() == expected_html
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
    # Existing secure, reviewed buyer-admin evidence reader. An attestation
    # cannot replace fresh independently observed Ringba routing/tracking.
    admin_ani, admin_recording = verified_buyer_admin_proof(
        evidence_root, now=now,
    )
    # Read the recorded direct founder-witnessed voice connection and buyer
    # route/ANI statements in their truthful scope. They cannot certify an
    # independently observed Ringba CallRoutes API, recording law or payout.
    witness = None
    try:
        from empire_os.lead_smart_site_handoff import CAMPAIGN, NUMBER
        control = load(evidence_root / 'pilot/approved_control.json')
        witness = load(repo_root / 'docs/evidence/lead_smart_founder_connected_voice_attestation_20261019.json')
        if (witness.get('schema_version') != 'empire.lead_smart.founder_voice_connection_attestation.v1'
                or witness.get('evidence_source') != 'founder-direct-chat-20261019'
                or witness.get('campaign_id') != CAMPAIGN
                or witness.get('tracking_number') != NUMBER
                or witness.get('independent_ringba_admin_api_verified') is not False
                or witness.get('recording_legal_release_certified') is not False
                or witness.get('payable_call_verified') is not False):
            raise ValueError('untrusted_witness_record')
        supervised_confirmation = {
            'buyer': witness.get('buyer'),
            'campaign_id': witness.get('campaign_id'),
            'tracking_number': witness.get('tracking_number'),
            'source_ref': witness.get('buyer_source_ref'),
            'buyer_confirmed_direct_route': witness.get('buyer_confirmed_direct_route'),
            'buyer_confirmed_original_ani': witness.get('buyer_confirmed_original_ani'),
            'founder_witnessed_voice_connection': witness.get('founder_witnessed_voice_connection'),
            'independently_proven_admin_api': witness.get('independent_ringba_admin_api_verified'),
            'founder_authority_ref': control.get('founder_authority_ref'),
            'starts_at': control.get('starts_at'),
            'ends_at': control.get('ends_at'),
        }
    except (OSError, RuntimeError, ValueError, TypeError, KeyError):
        supervised_confirmation = None
    # Read-only, exact-byte review of the actually deployed pre-dial consent
    # handler and call-specific privacy notice. This is not a statement that
    # the buyer's Ringba admin permissions or legal certification were obtained.
    consent_source = repo_root / 'empire_os/lead_smart_pilot_call_api.py'
    try:
        from empire_os.empire_ai_public_legal_release import checked_legal_path
        consent_sha = None if consent_source.is_symlink() else hashlib.sha256(consent_source.read_bytes()).hexdigest()
        if not isinstance(witness, dict) or witness.get('recording_legal_release_certified') is not False:
            raise ValueError('legal_certification_not_supported')
        published_policies = all(checked_legal_path(route) is not None
                                 for route in ('privacy','terms'))
        supervised_consumer_disclosure = {
            'mandatory_recording_source_ref': witness.get('mandatory_recording_buyer_source_ref'),
            'buyer_disclaimer_test_ref': witness.get('recording_notice_test_ref'),
            'buyer_deletion_source_ref': witness.get('deletion_if_legally_required_buyer_source_ref'),
            'buyer_mandatory_recording': witness.get('buyer_recording_is_mandatory'),
            'buyer_deletes_if_legally_required': witness.get('buyer_agreed_to_required_deletion'),
            'pre_dial_affirmative_consent_proven': witness.get('caller_pre_dial_site_consent_is_present'),
            'specific_call_privacy_notice_live': witness.get('public_website_specific_call_privacy_notice_present'),
            'general_privacy_terms_live': published_policies,
            'call_api_exact_sha256': consent_sha,
            'buyer_admin_configuration_proven': witness.get('independent_ringba_admin_api_verified'),
            'legal_compliance_certified': witness.get('recording_legal_release_certified'),
        }
    except (OSError, ValueError, TypeError, AttributeError):
        supervised_consumer_disclosure = None
    return build_launch_readiness(
        supervised_buyer_confirmation=supervised_confirmation,
        supervised_consumer_disclosure=supervised_consumer_disclosure,
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
            or admin_ani is True
        ),

        buyer_landing_page_approved=approved_candidate_matches(
            policy["routing"]["landing_review_report"], root=repo_root
        ),

        legal_release_verified=effective_legal_release_verified(),

        # A published recording notice and buyer acknowledgement alone are
        # insufficient. Only a source-reviewed, securely owned record with
        # verified responsible-party, consent, retention and legal checks
        # can release this separate recording gate.
        recording_notice_and_retention_verified=admin_recording,

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
