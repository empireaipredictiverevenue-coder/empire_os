"""Fail-closed Google Search Console adapter contract and credential gate."""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence


@dataclass(frozen=True)
class SearchConsoleStatus:
    enabled: bool
    configured: bool
    available: bool
    reason: str
    site_url: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class SearchConsoleAdapter(Protocol):
    def status(self) -> SearchConsoleStatus:
        ...

    def observations(
        self,
        *,
        start_date: str,
        end_date: str,
        limit: int = 1000,
    ) -> Sequence[Mapping[str, Any]]:
        ...


class DisabledSearchConsoleAdapter:
    """Default adapter: no credentials, no network, no fabricated data."""

    def __init__(self, status: SearchConsoleStatus):
        self._status = status

    def status(self) -> SearchConsoleStatus:
        return self._status

    def observations(
        self,
        *,
        start_date: str,
        end_date: str,
        limit: int = 1000,
    ) -> Sequence[Mapping[str, Any]]:
        return ()


def _enabled(value: str | None) -> bool:
    return str(value or "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def search_console_status_from_env() -> SearchConsoleStatus:
    enabled = _enabled(os.getenv("EMPIRE_SEARCH_CONSOLE_ENABLED"))
    site_url = os.getenv(
        "EMPIRE_SEARCH_CONSOLE_SITE_URL", ""
    ).strip() or None
    credential_file = os.getenv(
        "EMPIRE_SEARCH_CONSOLE_CREDENTIAL_FILE", ""
    ).strip()

    if not enabled:
        return SearchConsoleStatus(
            enabled=False,
            configured=False,
            available=False,
            reason="disabled",
            site_url=site_url,
        )

    if not site_url or not credential_file:
        return SearchConsoleStatus(
            enabled=True,
            configured=False,
            available=False,
            reason="missing_required_binding",
            site_url=site_url,
        )

    path = Path(credential_file).expanduser()
    if not path.is_file():
        return SearchConsoleStatus(
            enabled=True,
            configured=False,
            available=False,
            reason="credential_file_unavailable",
            site_url=site_url,
        )

    return SearchConsoleStatus(
        enabled=True,
        configured=True,
        available=False,
        reason="adapter_activation_not_approved",
        site_url=site_url,
    )


def configured_search_console_adapter() -> SearchConsoleAdapter:
    return DisabledSearchConsoleAdapter(
        search_console_status_from_env()
    )
