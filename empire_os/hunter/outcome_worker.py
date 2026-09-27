"""Canonical outcome learner for Empire Hunter."""
from __future__ import annotations

import urllib.parse
from typing import Any, Callable

from empire_os.qualification_worker_v2 import request_json


RequestFn = Callable[..., Any]

EVENT_MAP = {
    "delivered": ("verified", 0.99, "contact_delivered"),
    "reply_received": ("verified", 0.99, "contact_replied"),
    "bounced": ("invalid", 0.05, "contact_bounced"),
    "complained": ("suppressed", 0.01, "contact_complained"),
    "suppressed": ("suppressed", 0.02, "contact_suppressed"),
}


class HunterOutcomeWorker:
    def __init__(self, *, request_factory: RequestFn = request_json):
        self._request = request_factory

    def _get(
        self,
        path: str,
        params: dict[str, str],
    ) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode(params)
        rows = self._request("GET", f"{path}?{query}") or []
        if not isinstance(rows, list):
            raise RuntimeError(f"invalid canonical response for {path}")
        return [row for row in rows if isinstance(row, dict)]

    def _patch(
        self,
        path: str,
        params: dict[str, str],
        payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode(params)
        rows = self._request(
            "PATCH",
            f"{path}?{query}",
            payload=payload,
            prefer="return=representation",
        ) or []
        if not isinstance(rows, list):
            raise RuntimeError(f"invalid canonical patch response for {path}")
        return [row for row in rows if isinstance(row, dict)]

    def _post(
        self,
        path: str,
        payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        rows = self._request(
            "POST",
            path,
            payload=payload,
            prefer="return=representation",
        ) or []
        if not isinstance(rows, list):
            raise RuntimeError(f"invalid canonical write response for {path}")
        return [row for row in rows if isinstance(row, dict)]

    @staticmethod
    def _mapped_event(row: dict[str, Any]):
        event_type = str(row.get("event_type") or "").strip().lower()
        if event_type in EVENT_MAP:
            return EVENT_MAP[event_type]

        if event_type == "failed":
            payload = row.get("payload")
            payload = payload if isinstance(payload, dict) else {}
            provider_event = str(
                payload.get("provider_event")
                or payload.get("status")
                or payload.get("event_type")
                or ""
            ).strip().lower()
            if provider_event in {"bounced", "bounce"}:
                return ("invalid", 0.05, "contact_bounced")
            if provider_event in {"complained", "spam_complaint"}:
                return ("suppressed", 0.01, "contact_complained")
        return None

    def _intent(self, intent_id: str) -> dict[str, Any] | None:
        rows = self._get(
            "/rest/v1/outbound_intents",
            {
                "select": (
                    "id,prospect_id,entity_id,normalized_recipient,"
                    "channel,status"
                ),
                "id": f"eq.{intent_id}",
                "limit": "1",
            },
        )
        return rows[0] if rows else None

    def _contacts(
        self,
        email: str,
    ) -> list[dict[str, Any]]:
        return self._get(
            "/rest/v1/intelligence_contact_points",
            {
                "select": (
                    "id,person_id,entity_id,verification_state,"
                    "confidence,verified_at,last_seen_at"
                ),
                "contact_type": "eq.work_email",
                "normalized_value": f"eq.{email}",
                "limit": "25",
            },
        )

    def _outcome_exists(
        self,
        *,
        entity_id: str | None,
        person_id: str | None,
        outcome_type: str,
        occurred_at: str,
        source_event_id: str,
    ) -> bool:
        filters = {
            "select": "id,outcome_value",
            "outcome_type": f"eq.{outcome_type}",
            "occurred_at": f"eq.{occurred_at}",
            "source_system": "eq.empire_hunter",
            "limit": "50",
        }
        if entity_id:
            filters["entity_id"] = f"eq.{entity_id}"
        if person_id:
            filters["person_id"] = f"eq.{person_id}"
        rows = self._get(
            "/rest/v1/intelligence_outcomes",
            filters,
        )
        for row in rows:
            value = row.get("outcome_value")
            if isinstance(value, dict) and str(
                value.get("source_event_id") or ""
            ) == source_event_id:
                return True
        return False

    def run(
        self,
        *,
        limit: int = 100,
        write_authorized: bool = False,
    ) -> dict[str, Any]:
        bounded = max(1, min(int(limit), 500))
        events = self._get(
            "/rest/v1/outbound_events",
            {
                "select": (
                    "id,intent_id,event_type,provider_message_id,"
                    "payload,occurred_at"
                ),
                "event_type": (
                    "in.(delivered,bounced,complained,failed,"
                    "reply_received,suppressed)"
                ),
                "order": "occurred_at.desc",
                "limit": str(bounded),
            },
        )

        observed = 0
        contacts_matched = 0
        contacts_updated = 0
        outcomes_written = 0
        skipped = 0

        for event in events:
            mapped = self._mapped_event(event)
            if mapped is None:
                skipped += 1
                continue
            new_state, confidence, outcome_type = mapped

            intent = self._intent(str(event.get("intent_id") or ""))
            if not intent or str(intent.get("channel") or "") != "email":
                skipped += 1
                continue
            email = str(
                intent.get("normalized_recipient") or ""
            ).strip().lower()
            if not email:
                skipped += 1
                continue

            observed += 1
            contacts = self._contacts(email)
            contacts_matched += len(contacts)
            if not write_authorized:
                continue

            occurred_at = str(event.get("occurred_at") or "").strip()
            source_event_id = str(event.get("id") or "").strip()

            if not contacts:
                intent_entity_id = (
                    str(intent.get("entity_id"))
                    if intent.get("entity_id")
                    else None
                )
                if not self._outcome_exists(
                    entity_id=intent_entity_id,
                    person_id=None,
                    outcome_type=outcome_type,
                    occurred_at=occurred_at,
                    source_event_id=source_event_id,
                ):
                    self._post(
                        "/rest/v1/intelligence_outcomes",
                        {
                            "entity_id": intent_entity_id,
                            "person_id": None,
                            "opportunity_id": None,
                            "outcome_type": outcome_type,
                            "outcome_value": {
                                "email": email,
                                "domain": (
                                    email.rsplit("@", 1)[1]
                                    if "@" in email
                                    else None
                                ),
                                "prospect_id": intent.get("prospect_id"),
                                "source_event_id": source_event_id,
                                "provider_message_id": event.get(
                                    "provider_message_id"
                                ),
                                "verified": True,
                                "contact_graph_match": False,
                                "commercial_revenue": False,
                            },
                            "occurred_at": occurred_at,
                            "source_system": "empire_hunter",
                        },
                    )
                    outcomes_written += 1
                continue

            for contact in contacts:
                patch = {
                    "verification_state": new_state,
                    "confidence": confidence,
                    "last_seen_at": occurred_at,
                }
                if new_state == "verified":
                    patch["verified_at"] = (
                        contact.get("verified_at") or occurred_at
                    )
                self._patch(
                    "/rest/v1/intelligence_contact_points",
                    {"id": f"eq.{contact['id']}"},
                    patch,
                )
                contacts_updated += 1

                entity_id = (
                    str(contact.get("entity_id"))
                    if contact.get("entity_id")
                    else None
                )
                person_id = (
                    str(contact.get("person_id"))
                    if contact.get("person_id")
                    else None
                )
                if self._outcome_exists(
                    entity_id=entity_id,
                    person_id=person_id,
                    outcome_type=outcome_type,
                    occurred_at=occurred_at,
                    source_event_id=source_event_id,
                ):
                    continue

                self._post(
                    "/rest/v1/intelligence_outcomes",
                    {
                        "entity_id": entity_id,
                        "person_id": person_id,
                        "opportunity_id": None,
                        "outcome_type": outcome_type,
                        "outcome_value": {
                            "email": email,
                            "source_event_id": source_event_id,
                            "provider_message_id": event.get(
                                "provider_message_id"
                            ),
                            "verified": True,
                            "commercial_revenue": False,
                        },
                        "occurred_at": occurred_at,
                        "source_system": "empire_hunter",
                    },
                )
                outcomes_written += 1

        return {
            "schema_version": "empire_hunter_outcomes.v1",
            "mode": (
                "INTERNAL_MATERIALIZE"
                if write_authorized
                else "OBSERVE"
            ),
            "write_authorized": write_authorized,
            "events_seen": len(events),
            "verified_events_observed": observed,
            "contacts_matched": contacts_matched,
            "contacts_updated": contacts_updated,
            "outcomes_written": outcomes_written,
            "skipped": skipped,
            "outbound_actions": False,
            "payment_actions": False,
            "revenue_actions": False,
        }
