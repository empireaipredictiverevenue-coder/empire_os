"""Registry for bounded Empire Revenue Actors."""
from __future__ import annotations

from typing import Any, Callable, Mapping

from empire_os.intent_brain_actor import (
    DESCRIPTOR as INTENT_BRAIN_DESCRIPTOR,
    run_intent_brain_actor,
)
from empire_os.first_party_identity_actor import (
    DESCRIPTOR as FIRST_PARTY_IDENTITY_DESCRIPTOR,
    run_first_party_identity_actor,
)
from empire_os.business_identity_actor import (
    DESCRIPTOR as BUSINESS_IDENTITY_DESCRIPTOR,
    run_business_identity_actor,
)


ActorRunner = Callable[
    [Mapping[str, Any]],
    dict[str, Any],
]


_ACTORS: dict[str, tuple[Any, ActorRunner]] = {
    INTENT_BRAIN_DESCRIPTOR.actor_key: (
        INTENT_BRAIN_DESCRIPTOR,
        run_intent_brain_actor,
    ),
    FIRST_PARTY_IDENTITY_DESCRIPTOR.actor_key: (
        FIRST_PARTY_IDENTITY_DESCRIPTOR,
        run_first_party_identity_actor,
    ),
    BUSINESS_IDENTITY_DESCRIPTOR.actor_key: (
        BUSINESS_IDENTITY_DESCRIPTOR,
        run_business_identity_actor,
    ),
}


def actor_catalog() -> list[dict[str, Any]]:
    return [
        descriptor.as_dict()
        for descriptor, _runner in _ACTORS.values()
    ]


def run_registered_actor(
    actor_key: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    row = _ACTORS.get(str(actor_key).strip())
    if row is None:
        raise KeyError(f"unknown revenue actor: {actor_key}")

    _descriptor, runner = row
    return runner(payload)
