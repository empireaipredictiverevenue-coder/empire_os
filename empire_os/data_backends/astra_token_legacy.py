"""Legacy hosted token backend for the Astra observer.

Vendor-specific HTTP mechanics are isolated here during EmpireDB migration.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from empire_os.outcome_role_transport import OutcomeTransportError
from empire_os.legacy_data_egress import (
    close_legacy_data_egress_circuit,
    open_legacy_data_egress_circuit,
    reserve_legacy_data_request,
)


LEGACY_ASTRA_RPC_MAP = {
    "get_commercial_outcome_feedback": (
        "get_commercial_outcome_feedback_token",
        ("p_limit",),
    ),
    "get_astra_operational_evidence": (
        "get_astra_operational_evidence_token",
        (),
    ),
}


class LegacyAstraTokenBackend:
    def __init__(
        self,
        base_url: str,
        publishable_key: str,
        token_file: str | Path,
        *,
        opener: Callable[..., Any] | None = None,
    ):
        self.base_url = str(base_url or "").strip().rstrip("/")
        self.publishable_key = str(publishable_key or "").strip()
        self.token_file = Path(token_file)
        self._open = opener or urlopen

        if not self.base_url.startswith("https://"):
            raise OutcomeTransportError(
                "legacy Astra RPC URL must use HTTPS"
            )
        if not self.publishable_key:
            raise OutcomeTransportError(
                "legacy Astra publishable key required"
            )
        if not self.token_file.is_file():
            raise OutcomeTransportError(
                "Astra observer token file required"
            )

    def _token(self) -> str:
        token = self.token_file.read_text(
            encoding="utf-8"
        ).strip()
        if len(token) < 32:
            raise OutcomeTransportError(
                "Astra observer token is invalid"
            )
        return token

    def call(
        self,
        name: str,
        params: dict[str, Any],
    ) -> Any:
        if name not in LEGACY_ASTRA_RPC_MAP:
            raise OutcomeTransportError(
                f"legacy Astra backend does not map {name}"
            )

        rpc_name, keys = LEGACY_ASTRA_RPC_MAP[name]
        if set(params) != set(keys):
            raise OutcomeTransportError(
                "unexpected Astra RPC parameters"
            )

        payload = {"p_token": self._token()}
        for key in keys:
            payload[key] = params[key]

        reserve_legacy_data_request()

        request = Request(
            f"{self.base_url}/rest/v1/rpc/{rpc_name}",
            data=json.dumps(
                payload,
                separators=(",", ":"),
            ).encode("utf-8"),
            headers={
                "apikey": self.publishable_key,
                "Authorization": (
                    f"Bearer {self.publishable_key}"
                ),
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "EmpireOS/astra-observer",
                "X-Empire-Component": "astra-observer",
            },
            method="POST",
        )

        try:
            with self._open(
                request,
                timeout=15,
            ) as response:
                raw = response.read().decode("utf-8")
                close_legacy_data_egress_circuit()
        except HTTPError as exc:
            body = exc.read().decode(
                "utf-8",
                errors="replace",
            )
            if (
                exc.code == 402
                and (
                    "exceed_egress_quota" in body
                    or "restricted due to the following violations"
                    in body
                )
            ):
                open_legacy_data_egress_circuit(
                    "exceed_egress_quota"
                )
            raise OutcomeTransportError(
                "token-authenticated Astra RPC failed"
            ) from exc
        except (URLError, OSError) as exc:
            raise OutcomeTransportError(
                "token-authenticated Astra RPC failed"
            ) from exc

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OutcomeTransportError(
                "token-authenticated Astra RPC returned invalid JSON"
            ) from exc



def legacy_astra_backend_from_environment(
    environ: Mapping[str, str],
    *,
    opener: Callable[..., Any] | None = None,
) -> LegacyAstraTokenBackend | None:
    """Build the migration backend from generic or legacy env names."""

    url = str(
        environ.get("EMPIRE_ASTRA_LEGACY_URL")
        or environ.get("EMPIRE_ASTRA_SUPABASE_URL")
        or ""
    ).strip()
    key = str(
        environ.get("EMPIRE_ASTRA_LEGACY_PUBLISHABLE_KEY")
        or environ.get("EMPIRE_ASTRA_SUPABASE_PUBLISHABLE_KEY")
        or ""
    ).strip()
    token_file = str(
        environ.get("EMPIRE_ASTRA_OBSERVER_TOKEN_FILE")
        or ""
    ).strip()

    if not (url or key or token_file):
        return None
    if not (url and key and token_file):
        raise OutcomeTransportError(
            "incomplete token-authenticated Astra RPC config"
        )
    return LegacyAstraTokenBackend(
        url,
        key,
        token_file,
        opener=opener,
    )
