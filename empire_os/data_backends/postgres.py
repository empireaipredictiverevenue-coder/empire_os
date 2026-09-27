"""Private PostgreSQL connector for Empire Data Cloud.

This module owns PostgreSQL connection configuration and bounded health/session
primitives. It deliberately does not expose an arbitrary-SQL public API.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from typing import Any, Callable, Mapping, Protocol


class ConnectionLike(Protocol):
    def execute(self, query: str, params: tuple[object, ...] = ()) -> Any:
        ...

    def close(self) -> None:
        ...


ConnectFactory = Callable[..., ConnectionLike]


@dataclass(frozen=True)
class PostgresConnectionConfig:
    dsn: str
    application_name: str = "empire-data-cloud"
    connect_timeout_seconds: int = 5
    statement_timeout_ms: int = 5000
    private_network_required: bool = True
    public_database_port_allowed: bool = False

    def validate(self) -> None:
        if not self.dsn.strip():
            raise ValueError("EmpireDB DSN is required")
        if not self.application_name.strip():
            raise ValueError("application_name is required")
        if self.connect_timeout_seconds < 1:
            raise ValueError("connect timeout must be positive")
        if self.statement_timeout_ms < 1:
            raise ValueError("statement timeout must be positive")
        if not self.private_network_required:
            raise ValueError("EmpireDB requires private networking")
        if self.public_database_port_allowed:
            raise ValueError("public EmpireDB database ports are forbidden")

    def safe_snapshot(self) -> dict[str, Any]:
        self.validate()
        payload = asdict(self)
        payload.pop("dsn", None)
        payload["dsn_configured"] = True
        return payload

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> "PostgresConnectionConfig":
        source = os.environ if environ is None else environ
        dsn = str(source.get("EMPIREDB_DSN") or "").strip()
        config = cls(dsn=dsn)
        config.validate()
        return config


def _default_connect_factory(**kwargs: Any) -> ConnectionLike:
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError(
            "psycopg is required for EmpireDB runtime connectivity; "
            "install the existing payment-ops optional dependency"
        ) from exc
    return psycopg.connect(**kwargs)


class PostgresConnector:
    """Bounded connector. Consumers receive sessions, not raw credentials."""

    def __init__(
        self,
        config: PostgresConnectionConfig,
        *,
        connect_factory: ConnectFactory | None = None,
    ) -> None:
        config.validate()
        self._config = config
        self._connect_factory = connect_factory or _default_connect_factory

    @property
    def config_snapshot(self) -> dict[str, Any]:
        return self._config.safe_snapshot()

    def _open_connection(self) -> ConnectionLike:
        """Open an internal application-labelled session.

        Raw sessions are intentionally not part of the public adapter API.
        Repository implementations may be added inside this backend package
        without exposing arbitrary SQL through the Data Cloud API.
        """
        connection = self._connect_factory(
            conninfo=self._config.dsn,
            connect_timeout=self._config.connect_timeout_seconds,
            application_name=self._config.application_name,
        )
        try:
            connection.execute(
                "SELECT set_config('statement_timeout', %s, false)",
                (str(self._config.statement_timeout_ms),),
            )
            return connection
        except Exception:
            connection.close()
            raise

    def health(self) -> dict[str, Any]:
        connection: ConnectionLike | None = None
        try:
            connection = self._open_connection()
            row = connection.execute(
                "SELECT current_database(), pg_is_in_recovery()"
            ).fetchone()
            database = row[0] if row else None
            in_recovery = bool(row[1]) if row and len(row) > 1 else None
            return {
                "schema_version": "empire.postgres-backend-health.v1",
                "healthy": True,
                "database": database,
                "in_recovery": in_recovery,
                "config": self.config_snapshot,
                "authority": {
                    "schema_mutation": False,
                    "destructive_operation": False,
                    "production_cutover": False,
                },
            }
        except Exception as exc:
            return {
                "schema_version": "empire.postgres-backend-health.v1",
                "healthy": False,
                "database": None,
                "in_recovery": None,
                "error_class": type(exc).__name__,
                "config": self.config_snapshot,
                "authority": {
                    "schema_mutation": False,
                    "destructive_operation": False,
                    "production_cutover": False,
                },
            }
        finally:
            if connection is not None:
                connection.close()
