"""Core evidence models for Empire Hunter."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class VerificationState(str, Enum):
    CONFIRMED = "confirmed"
    PROBABLE = "probable"
    UNKNOWN = "unknown"
    REJECTED = "rejected"


@dataclass(frozen=True)
class ContactEvidence:
    email: str
    state: VerificationState
    confidence: float
    source: str
    source_url: str | None = None
    person_name: str | None = None
    person_title: str | None = None
    person_bound: bool = False
    first_party: bool = False
    syntax_ok: bool = False
    mx_ok: bool = False
    mailbox_status: str = "not_checked"
    delivered_evidence: bool = False
    bounced_evidence: bool = False
    role_address: bool = False
    disposable: bool = False
    reasons: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["state"] = self.state.value
        return data


@dataclass(frozen=True)
class DomainPattern:
    domain: str
    pattern: str | None
    observations: int
    agreement: float
    confidence: float
    source: str = "first_party_observations"

    @property
    def learned(self) -> bool:
        return bool(self.pattern and self.observations > 0)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
