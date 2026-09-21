"""Fail-closed Google Search Console adapter and credential gate."""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence
from urllib.parse import quote

import requests


SEARCH_CONSOLE_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"


class SearchConsoleUnavailable(RuntimeError):
    pass


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

    def daily_observations(
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
        raise SearchConsoleUnavailable(self._status.reason)

    def daily_observations(
        self,
        *,
        start_date: str,
        end_date: str,
        limit: int = 1000,
    ) -> Sequence[Mapping[str, Any]]:
        raise SearchConsoleUnavailable(self._status.reason)


TokenProvider = Callable[[Path], str]
PostJson = Callable[[str, Mapping[str, str], Mapping[str, Any]], Mapping[str, Any]]


def _enabled(value: str | None) -> bool:
    return str(value or "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _service_account_token(path: Path) -> str:
    try:
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account
    except ImportError as exc:
        raise SearchConsoleUnavailable(
            "google_auth_dependency_unavailable"
        ) from exc

    credentials = service_account.Credentials.from_service_account_file(
        str(path),
        scopes=[SEARCH_CONSOLE_SCOPE],
    )
    credentials.refresh(Request())
    if not credentials.token:
        raise SearchConsoleUnavailable("access_token_unavailable")
    return str(credentials.token)


def _post_json(
    url: str,
    headers: Mapping[str, str],
    payload: Mapping[str, Any],
) -> Mapping[str, Any]:
    response = requests.post(
        url,
        headers=dict(headers),
        json=dict(payload),
        timeout=20,
    )
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, Mapping):
        raise SearchConsoleUnavailable("invalid_search_console_response")
    return body


class GoogleSearchConsoleAdapter:
    """Read-only Search Console Search Analytics transport."""

    def __init__(
        self,
        site_url: str,
        credential_file: str | Path,
        *,
        token_provider: TokenProvider | None = None,
        post_json: PostJson | None = None,
    ) -> None:
        self.site_url = str(site_url).strip()
        self.credential_file = Path(credential_file).expanduser()
        self._token_provider = token_provider or _service_account_token
        self._post_json = post_json or _post_json

    def status(self) -> SearchConsoleStatus:
        return SearchConsoleStatus(
            enabled=True,
            configured=True,
            available=True,
            reason="ready",
            site_url=self.site_url,
        )

    def observations(
        self,
        *,
        start_date: str,
        end_date: str,
        limit: int = 1000,
    ) -> Sequence[Mapping[str, Any]]:
        row_limit = max(1, min(int(limit), 25_000))
        token = self._token_provider(self.credential_file)
        endpoint = (
            "https://searchconsole.googleapis.com/webmasters/v3/sites/"
            + quote(self.site_url, safe="")
            + "/searchAnalytics/query"
        )
        body = self._post_json(
            endpoint,
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            {
                "startDate": str(start_date),
                "endDate": str(end_date),
                "dimensions": ["query", "page"],
                "rowLimit": row_limit,
            },
        )
        rows = body.get("rows") or ()
        if not isinstance(rows, (list, tuple)):
            raise SearchConsoleUnavailable("invalid_search_console_rows")
        return tuple(dict(row) for row in rows if isinstance(row, Mapping))

    def daily_observations(
        self,
        *,
        start_date: str,
        end_date: str,
        limit: int = 1000,
    ) -> Sequence[Mapping[str, Any]]:
        row_limit = max(1, min(int(limit), 25_000))
        token = self._token_provider(self.credential_file)
        endpoint = (
            "https://searchconsole.googleapis.com/webmasters/v3/sites/"
            + quote(self.site_url, safe="")
            + "/searchAnalytics/query"
        )
        body = self._post_json(
            endpoint,
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            {
                "startDate": str(start_date),
                "endDate": str(end_date),
                "dimensions": ["date"],
                "rowLimit": row_limit,
            },
        )
        rows = body.get("rows") or ()
        if not isinstance(rows, (list, tuple)):
            raise SearchConsoleUnavailable("invalid_search_console_rows")
        return tuple(dict(row) for row in rows if isinstance(row, Mapping))


def search_console_status_from_env() -> SearchConsoleStatus:
    enabled = _enabled(os.getenv("EMPIRE_SEARCH_CONSOLE_ENABLED"))
    approved = _enabled(os.getenv("EMPIRE_SEARCH_CONSOLE_ACTIVATION_APPROVED"))
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

    if not approved:
        return SearchConsoleStatus(
            enabled=True,
            configured=True,
            available=False,
            reason="adapter_activation_not_approved",
            site_url=site_url,
        )

    return SearchConsoleStatus(
        enabled=True,
        configured=True,
        available=True,
        reason="ready",
        site_url=site_url,
    )


def configured_search_console_adapter() -> SearchConsoleAdapter:
    status = search_console_status_from_env()
    if not status.available:
        return DisabledSearchConsoleAdapter(status)
    credential_file = os.getenv(
        "EMPIRE_SEARCH_CONSOLE_CREDENTIAL_FILE", ""
    ).strip()
    return GoogleSearchConsoleAdapter(
        status.site_url or "",
        credential_file,
    )
