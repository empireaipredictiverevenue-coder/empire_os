import base64
import json
from datetime import datetime, timezone

import pytest

from empire_os.lead_smart_coverage_observer import (
    PublicContract,
    build_delta,
    build_snapshot,
    extract_public_credential,
    select_canonical_roofing_vertical,
)


def fake_anon_jwt() -> str:
    def enc(value):
        raw = json.dumps(
            value,
            separators=(",", ":"),
        ).encode()

        return (
            base64.urlsafe_b64encode(raw)
            .decode()
            .rstrip("=")
        )

    return ".".join([
        enc({"alg": "HS256", "typ": "JWT"}),
        enc({"role": "anon"}),
        "signature",
    ])


def contract():
    return PublicContract(
        host="https://example.supabase.co",
        public_key="not-persisted",
        public_key_kind="anon_jwt",
        bundle_url="https://example/app.js",
        bundle_sha256="a" * 64,
    )


def roofing_rows():
    return [
        {
            "zip": "00501",
            "city": "Holtsville",
            "state": "NY",
            "offer_key": "roofing",
            "offer_name":
                "Main Roofing Contractors - Nationwide - Variable Rate",
            "duration_payout": 40.0,
            "cpl_payout": None,
            "top_payout": 40.0,
            "last_updated":
                "2026-10-06T14:00:00+00:00",
        },
        {
            "zip": "01001",
            "city": "Agawam",
            "state": "MA",
            "offer_key": "roofing",
            "offer_name":
                "Main Roofing Contractors - Nationwide - Variable Rate",
            "duration_payout": 60.0,
            "cpl_payout": None,
            "top_payout": 60.0,
            "last_updated":
                "2026-10-06T14:01:00+00:00",
        },
    ]


def test_exact_roofing_selector_excludes_cpl_and_waterproofing():
    rows = [
        {
            "enabled": False,
            "slug": "roofing-cpl",
            "offer_key": "roofing",
            "group_label":
                "CPL Call (Pay on Appointment)",
        },
        {
            "enabled": True,
            "slug": "roofing",
            "offer_key": "roofing",
            "group_label": "Pay-per-Call",
            "name": "Roofing",
        },
        {
            "enabled": True,
            "slug": "waterproofing-cpl",
            "offer_key": "waterproofing",
            "group_label":
                "CPL Call (Pay on Appointment)",
        },
    ]

    selected = select_canonical_roofing_vertical(
        rows
    )

    assert selected["slug"] == "roofing"
    assert selected["offer_key"] == "roofing"
    assert selected["enabled"] is True


def test_snapshot_preserves_leading_zero_zip_and_is_fail_closed():
    vertical = {
        "id": "roof-1",
        "slug": "roofing",
        "name": "Roofing",
        "enabled": True,
        "group_label": "Pay-per-Call",
        "offer_key": "roofing",
        "offer_name":
            "Main Roofing Contractors - Nationwide - Variable Rate",
    }

    snapshot = build_snapshot(
        contract=contract(),
        vertical=vertical,
        rows=roofing_rows(),
        content_range="0-1/2",
        observed_at=datetime(
            2026,
            10,
            6,
            15,
            0,
            tzinfo=timezone.utc,
        ),
    )

    assert snapshot["rows"][0]["zip"] == "00501"
    assert snapshot["coverage"]["row_count"] == 2
    assert snapshot["coverage"]["unique_zip_count"] == 2

    authority = snapshot["authority"]

    assert authority["zip_coverage_observed"] is True
    assert (
        authority["zip_coverage_activation_verified"]
        is False
    )
    assert authority["tracking_verified"] is False
    assert authority["routing_verified"] is False
    assert authority["routing_enabled"] is False
    assert authority["traffic_enabled"] is False
    assert authority["execution_authority"] == "NONE"

    serialized = json.dumps(snapshot)

    assert "not-persisted" not in serialized


def test_delta_detects_zip_and_payout_changes():
    vertical = {
        "id": "roof-1",
        "slug": "roofing",
        "name": "Roofing",
        "enabled": True,
        "group_label": "Pay-per-Call",
        "offer_key": "roofing",
        "offer_name": "Roofing",
    }

    previous = build_snapshot(
        contract=contract(),
        vertical=vertical,
        rows=roofing_rows(),
        content_range="0-1/2",
        observed_at=datetime(
            2026,
            10,
            6,
            15,
            0,
            tzinfo=timezone.utc,
        ),
    )

    current_rows = roofing_rows()
    current_rows[1] = {
        **current_rows[1],
        "top_payout": 75.0,
        "duration_payout": 75.0,
    }

    current_rows.append({
        **current_rows[0],
        "zip": "02108",
        "city": "Boston",
    })

    current = build_snapshot(
        contract=contract(),
        vertical=vertical,
        rows=current_rows,
        content_range="0-2/3",
        observed_at=datetime(
            2026,
            10,
            6,
            16,
            0,
            tzinfo=timezone.utc,
        ),
    )

    delta = build_delta(
        previous,
        current,
    )

    assert delta["baseline"] is False
    assert delta["source_changed"] is True
    assert delta["zip_added_count"] == 1
    assert delta["zip_removed_count"] == 0
    assert (
        delta["top_payout_changed_zip_count"]
        == 1
    )


def test_only_public_anon_credential_is_accepted():
    anon = fake_anon_jwt()

    kind, value = extract_public_credential(
        f'const publicKey="{anon}";'
    )

    assert kind == "anon_jwt"
    assert value == anon

    with pytest.raises(RuntimeError):
        extract_public_credential(
            'const secret="sb_secret_DO_NOT_ACCEPT";'
        )
