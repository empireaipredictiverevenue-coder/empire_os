"""
Carrier Application Portal Auto-Filler (#3).

Manages carrier application records and provides a stub for headless-browser
auto-fill. The actual fill logic is deferred until a headless browser (e.g.
Playwright/Selenium) is wired in; for now `auto_fill_application()` logs what
it would do and returns a structured fill plan.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("carrier_applications")

# ── Valid statuses ──────────────────────────────────────────────────
VALID_STATUSES = frozenset({"not_applied", "applied", "approved", "rejected"})

# ── Schema ──────────────────────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS carrier_applications (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT    NOT NULL,
    license_no   TEXT    NOT NULL,
    carrier      TEXT    NOT NULL,
    status       TEXT    NOT NULL DEFAULT 'not_applied'
                         CHECK(status IN ('not_applied','applied','approved','rejected')),
    url          TEXT    DEFAULT '',
    applied_at   TEXT,
    approved_at  TEXT,
    notes        TEXT    DEFAULT '',
    created_at   TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_carrier_apps_carrier
    ON carrier_applications(carrier, status);
"""

# ── DTOs ────────────────────────────────────────────────────────────


@dataclass
class CarrierApplication:
    id: int
    company_name: str
    license_no: str
    carrier: str
    status: str
    url: str
    applied_at: Optional[str]
    approved_at: Optional[str]
    notes: str
    created_at: str

    def to_dict(self) -> dict:
        return asdict(self)


# ── Errors ──────────────────────────────────────────────────────────


class CarrierAppError(Exception):
    """Base error for carrier application operations."""


class InvalidStatusError(CarrierAppError):
    """Raised when an invalid status is supplied."""


class ApplicationNotFoundError(CarrierAppError):
    """Raised when an application id does not exist."""


# ── Operations ──────────────────────────────────────────────────────


def _validate_status(status: str) -> str:
    if status not in VALID_STATUSES:
        raise InvalidStatusError(
            f"Invalid status '{status}'. Valid: {sorted(VALID_STATUSES)}"
        )
    return status


def ensure_schema(backend) -> None:
    """Create the carrier_applications table if it does not exist."""
    backend.executescript(SCHEMA_SQL)
    backend.commit()
    logger.info("carrier_applications schema ensured")


def create_application(
    backend,
    company_name: str,
    license_no: str,
    carrier: str,
) -> CarrierApplication:
    """Register intent to apply with a carrier.

    Returns the newly created CarrierApplication record.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")
    cursor = backend.execute(
        """INSERT INTO carrier_applications
           (company_name, license_no, carrier, status, created_at)
           VALUES (?, ?, ?, 'not_applied', ?)""",
        (company_name.strip(), license_no.strip(), carrier.strip(), now),
    )
    backend.commit()
    app_id = cursor.lastrowid
    logger.info(
        "Created carrier application id=%d company=%s carrier=%s",
        app_id, company_name, carrier,
    )
    return get_application(backend, app_id)


def get_application(backend, app_id: int) -> CarrierApplication:
    """Fetch a single application by id. Raises ApplicationNotFoundError."""
    cursor = backend.execute(
        "SELECT * FROM carrier_applications WHERE id = ?", (app_id,)
    )
    row = cursor.fetchone()
    if row is None:
        raise ApplicationNotFoundError(f"Application id={app_id} not found")
    return CarrierApplication(**dict(row))


def list_applications(
    backend,
    carrier: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
) -> list[CarrierApplication]:
    """Query applications, optionally filtered by carrier and/or status."""
    if status is not None:
        _validate_status(status)

    parts = ["SELECT * FROM carrier_applications WHERE 1=1"]
    params: list = []

    if carrier:
        parts.append("AND carrier = ?")
        params.append(carrier)
    if status:
        parts.append("AND status = ?")
        params.append(status)

    parts.append("ORDER BY id DESC LIMIT ?")
    params.append(limit)

    cursor = backend.execute(" ".join(parts), tuple(params))
    return [CarrierApplication(**dict(r)) for r in cursor.fetchall()]


def update_application(
    backend,
    app_id: int,
    status: Optional[str] = None,
    notes: Optional[str] = None,
) -> CarrierApplication:
    """Update an application's status and/or notes.

    When transitioning to 'applied' or 'approved', the corresponding
    timestamp is set automatically.
    """
    app = get_application(backend, app_id)  # raises if not found

    updates: list[str] = []
    params: list = []

    if status is not None:
        _validate_status(status)
        updates.append("status = ?")
        params.append(status)

        if status == "applied":
            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")
            updates.append("applied_at = ?")
            params.append(now)
        elif status == "approved":
            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")
            updates.append("approved_at = ?")
            params.append(now)

    if notes is not None:
        updates.append("notes = ?")
        params.append(notes)

    if not updates:
        return app  # nothing to change

    params.append(app_id)
    backend.execute(
        f"UPDATE carrier_applications SET {', '.join(updates)} WHERE id = ?",
        tuple(params),
    )
    backend.commit()

    updated = get_application(backend, app_id)
    logger.info(
        "Updated application id=%d status=%s notes=%s",
        app_id, updated.status, bool(notes),
    )
    return updated


def auto_fill_application(backend, app_id: int) -> dict:
    """Generate a fill plan for an application (stub — no headless browser yet).

    Returns a structured dict describing what fields would be filled,
    what the agent would do, and what is needed to complete the fill.
    Actual browser automation (Playwright / Selenium) will be wired in
    when a headless-browser environment is available.
    """
    app = get_application(backend, app_id)

    if app.status != "not_applied":
        return {
            "ok": True,
            "app_id": app_id,
            "status": app.status,
            "message": f"Application already at '{app.status}'; no fill needed.",
            "fill_plan": None,
        }

    fill_plan = {
        "app_id": app_id,
        "company_name": app.company_name,
        "license_no": app.license_no,
        "carrier": app.carrier,
        "carrier_url_hint": _carrier_portal_hint(app.carrier),
        "fields_to_fill": [
            {"field": "company_name", "value": app.company_name, "selector_hint": "#company-name"},
            {"field": "license_no", "value": app.license_no, "selector_hint": "#license-number"},
            {"field": "business_type", "value": "Contractor", "selector_hint": "#business-type"},
        ],
        "steps": [
            "1. Navigate to carrier portal login page",
            "2. Authenticate (credentials must be provided externally)",
            "3. Navigate to 'New Application' or 'Apply Now' section",
            "4. Fill company name, license number, and business type",
            "5. Upload required documents (licence, insurance, bond)",
            "6. Review and submit",
            "7. Mark status as 'applied' in our system",
        ],
        "documents_required": [
            "State contractor license (PDF)",
            "General liability insurance certificate",
            "Worker's compensation insurance certificate",
            "Surety bond certificate",
        ],
        "note": (
            "Headless browser (Playwright/Selenium) not yet wired. "
            "This is a stub returning the fill plan only."
        ),
    }

    logger.info(
        "Auto-fill plan generated for application id=%d carrier=%s",
        app_id, app.carrier,
    )
    return {
        "ok": True,
        "app_id": app_id,
        "status": app.status,
        "message": "Fill plan generated (stub — browser automation pending)",
        "fill_plan": fill_plan,
    }


def _carrier_portal_hint(carrier: str) -> str:
    """Return a human-readable hint about where to find the carrier's portal."""
    hints = {
        "statefarm": "https://www.statefarm.com/agent/contractor-application",
        "allstate": "https://www.allstate.com/contractors/apply",
        "farmers": "https://www.farmers.com/agent-contractor-portal",
        "liberty mutual": "https://www.libertymutual.com/contractor-application",
        "nationwide": "https://www.nationwide.com/contractor-enrollment",
        "progressive": "https://www.progressivecommercial.com/contractor-signup",
        "travelers": "https://www.travelers.com/contractor-application",
        "usaa": "https://www.usaa.com/contractor-portal",
        "geico": "https://www.geico.com/contractor-application",
        "hartford": "https://www.thehartford.com/contractor-services",
    }
    return hints.get(carrier.lower().strip(), f"Look up '{carrier}' contractor portal manually")
