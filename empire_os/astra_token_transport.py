"""Token-authenticated HTTPS transport for the Phase 4 Astra observer."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from empire_os.outcome_role_transport import OutcomeTransportError


ASTRA_TOKEN_FUNCTIONS = {
    "get_commercial_outcome_feedback": (
        "get_commercial_outcome_feedback_token",
        ("p_limit",),
    ),
    "get_astra_operational_evidence": (
        "get_astra_operational_evidence_token",
        (),
    ),
}


class SupabaseTokenAstraRpc:
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
            raise OutcomeTransportError("Supabase Astra RPC URL must use HTTPS")
        if not self.publishable_key:
            raise OutcomeTransportError("Supabase publishable key required")
        if not self.token_file.is_file():
            raise OutcomeTransportError("Astra observer token file required")

    def _token(self) -> str:
        token = self.token_file.read_text(encoding="utf-8").strip()
        if len(token) < 32:
            raise OutcomeTransportError("Astra observer token is invalid")
        return token

    def __call__(self, name: str, params: dict[str, Any]) -> Any:
        if name not in ASTRA_TOKEN_FUNCTIONS:
            raise OutcomeTransportError(
                f"Astra observer is not allowed to execute {name}"
            )
        rpc_name, keys = ASTRA_TOKEN_FUNCTIONS[name]
        if not isinstance(params, dict) or set(params) != set(keys):
            raise OutcomeTransportError("unexpected Astra RPC parameters")

        payload = {"p_token": self._token()}
        for key in keys:
            payload[key] = params[key]
        request = Request(
            f"{self.base_url}/rest/v1/rpc/{rpc_name}",
            data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers={
                "apikey": self.publishable_key,
                "Authorization": f"Bearer {self.publishable_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with self._open(request, timeout=15) as response:
                raw = response.read().decode("utf-8")
        except (HTTPError, URLError, OSError) as exc:
            raise OutcomeTransportError(
                "token-authenticated Astra RPC failed"
            ) from exc

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OutcomeTransportError(
                "token-authenticated Astra RPC returned invalid JSON"
            ) from exc
