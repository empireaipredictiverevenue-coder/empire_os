"""Bounded Supabase materializer for Empire Hunter evidence."""
from __future__ import annotations

import urllib.parse
from typing import Any, Callable

from empire_os.hunter.evidence_graph import HunterEvidencePlan
from empire_os.qualification_worker_v2 import request_json


RequestFn = Callable[..., Any]
STATE_RANK = {
    "unknown": 0,
    "probable": 1,
    "confirmed": 2,
    "rejected": 3,
}


class HunterMaterializerError(RuntimeError):
    pass


class SupabaseHunterMaterializer:
    """Write only the canonical Intelligence Fabric tables Hunter owns."""

    def __init__(
        self,
        *,
        request_factory: RequestFn = request_json,
    ):
        self._request = request_factory

    def _get(
        self,
        path: str,
        params: dict[str, str],
    ) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode(params)
        rows = self._request("GET", f"{path}?{query}") or []
        if not isinstance(rows, list) or any(
            not isinstance(row, dict) for row in rows
        ):
            raise HunterMaterializerError(
                f"invalid canonical response for {path}"
            )
        return rows

    def _post(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        prefer: str = "return=representation",
    ) -> list[dict[str, Any]]:
        rows = self._request(
            "POST",
            path,
            payload=payload,
            prefer=prefer,
        ) or []
        if not isinstance(rows, list):
            raise HunterMaterializerError(
                f"invalid canonical write response for {path}"
            )
        return rows

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
            raise HunterMaterializerError(
                f"invalid canonical patch response for {path}"
            )
        return rows

    def _source_id(self, plan: HunterEvidencePlan) -> str:
        path = (
            "/rest/v1/intelligence_sources"
            "?on_conflict=source_key"
        )
        rows = self._post(
            path,
            {
                "source_key": plan.source_key,
                "source_type": plan.source_type,
                "display_name": plan.source_display_name,
                "authority_score": plan.source_authority_score,
                "enabled": True,
                "metadata": {
                    "owner": "empire_hunter",
                    "first_party": True,
                },
            },
            prefer=(
                "resolution=merge-duplicates,"
                "return=representation"
            ),
        )
        if len(rows) != 1 or not rows[0].get("id"):
            raise HunterMaterializerError(
                "could not resolve Empire Hunter source"
            )
        return str(rows[0]["id"])

    def _current_people(
        self,
        entity_id: str,
    ) -> list[dict[str, Any]]:
        employment = self._get(
            "/rest/v1/intelligence_employment",
            {
                "select": "person_id",
                "entity_id": f"eq.{entity_id}",
                "is_current": "eq.true",
                "limit": "100",
            },
        )
        person_ids = sorted({
            str(row.get("person_id"))
            for row in employment
            if row.get("person_id")
        })
        if not person_ids:
            return []
        return self._get(
            "/rest/v1/intelligence_people",
            {
                "select": (
                    "id,canonical_name,normalized_name,"
                    "identity_confidence"
                ),
                "id": f"in.({','.join(person_ids)})",
                "limit": "100",
            },
        )

    def _person_id(
        self,
        plan: HunterEvidencePlan,
        person,
        current_people: list[dict[str, Any]],
    ) -> str:
        matches = [
            row for row in current_people
            if str(row.get("normalized_name") or "")
            == person.normalized_name
        ]
        if len(matches) > 1:
            raise HunterMaterializerError(
                "ambiguous current person identity"
            )
        if len(matches) == 1:
            return str(matches[0]["id"])

        rows = self._post(
            "/rest/v1/intelligence_people",
            {
                "canonical_name": person.canonical_name,
                "normalized_name": person.normalized_name,
                "identity_confidence": person.identity_confidence,
            },
        )
        if len(rows) != 1 or not rows[0].get("id"):
            raise HunterMaterializerError(
                "could not create intelligence person"
            )
        current_people.append(rows[0])
        return str(rows[0]["id"])

    def _employment(
        self,
        *,
        person_id: str,
        row,
        observed_at: str,
    ) -> str:
        current = self._get(
            "/rest/v1/intelligence_employment",
            {
                "select": (
                    "id,title,normalized_title,is_current,"
                    "valid_from,valid_to,confidence"
                ),
                "person_id": f"eq.{person_id}",
                "entity_id": f"eq.{row.entity_id}",
                "is_current": "eq.true",
                "limit": "2",
            },
        )
        if len(current) > 1:
            raise HunterMaterializerError(
                "multiple current employment rows"
            )
        if current:
            existing = current[0]
            if (
                str(existing.get("normalized_title") or "")
                == row.normalized_title
            ):
                return str(existing["id"])
            self._patch(
                "/rest/v1/intelligence_employment",
                {"id": f"eq.{existing['id']}"},
                {
                    "is_current": False,
                    "valid_to": observed_at,
                },
            )

        rows = self._post(
            "/rest/v1/intelligence_employment",
            {
                "person_id": person_id,
                "entity_id": row.entity_id,
                "title": row.title,
                "normalized_title": row.normalized_title,
                "seniority": None,
                "department": None,
                "buying_role": None,
                "is_current": True,
                "valid_from": observed_at,
                "valid_to": None,
                "confidence": row.confidence,
            },
        )
        if len(rows) != 1 or not rows[0].get("id"):
            raise HunterMaterializerError(
                "could not create employment evidence"
            )
        return str(rows[0]["id"])

    def _contact(
        self,
        *,
        source_id: str,
        person_id: str | None,
        row,
        observed_at: str,
    ) -> tuple[str, str]:
        existing = self._get(
            "/rest/v1/intelligence_contact_points",
            {
                "select": (
                    "id,verification_state,confidence,verified_at,"
                    "last_seen_at"
                ),
                "entity_id": f"eq.{row.entity_id}",
                "contact_type": f"eq.{row.contact_type}",
                "normalized_value": f"eq.{row.normalized_value}",
                "source_id": f"eq.{source_id}",
                "limit": "2",
            },
        )
        if len(existing) > 1:
            raise HunterMaterializerError(
                "duplicate Hunter contact evidence"
            )
        if existing:
            current = existing[0]
            old_state = str(
                current.get("verification_state") or "unknown"
            )
            new_state = row.verification_state
            state = (
                new_state
                if new_state == "rejected"
                or STATE_RANK.get(new_state, 0)
                >= STATE_RANK.get(old_state, 0)
                else old_state
            )
            confidence = max(
                float(current.get("confidence") or 0.0),
                float(row.confidence),
            )
            verified_at = current.get("verified_at")
            if state == "confirmed" and not verified_at:
                verified_at = observed_at
            updated = self._patch(
                "/rest/v1/intelligence_contact_points",
                {"id": f"eq.{current['id']}"},
                {
                    "person_id": person_id,
                    "last_seen_at": observed_at,
                    "verification_state": state,
                    "verified_at": verified_at,
                    "confidence": confidence,
                },
            )
            if len(updated) != 1:
                raise HunterMaterializerError(
                    "could not refresh contact evidence"
                )
            return str(current["id"]), "updated"

        created = self._post(
            "/rest/v1/intelligence_contact_points",
            {
                "person_id": person_id,
                "entity_id": row.entity_id,
                "contact_type": row.contact_type,
                "value": row.value,
                "normalized_value": row.normalized_value,
                "verification_state": row.verification_state,
                "source_id": source_id,
                "first_seen_at": row.first_seen_at,
                "last_seen_at": row.last_seen_at,
                "verified_at": row.verified_at,
                "confidence": row.confidence,
            },
        )
        if len(created) != 1 or not created[0].get("id"):
            raise HunterMaterializerError(
                "could not create contact evidence"
            )
        return str(created[0]["id"]), "inserted"

    def _facts(
        self,
        *,
        source_id: str,
        plan: HunterEvidencePlan,
    ) -> int:
        inserted = 0
        for row in plan.facts:
            result = self._post(
                (
                    "/rest/v1/intelligence_facts"
                    "?on_conflict=evidence_hash"
                ),
                {
                    "entity_type": "company",
                    "entity_id": row.entity_id,
                    "fact_key": row.fact_key,
                    "fact_value": row.fact_value,
                    "source_id": source_id,
                    "confidence": row.confidence,
                    "first_seen_at": row.first_seen_at,
                    "last_seen_at": row.last_seen_at,
                    "valid_from": row.first_seen_at,
                    "valid_to": None,
                    "evidence_uri": row.evidence_uri,
                    "evidence_hash": row.evidence_hash,
                },
                prefer=(
                    "resolution=ignore-duplicates,"
                    "return=representation"
                ),
            )
            inserted += len(result)
        return inserted

    def materialize(
        self,
        plan: HunterEvidencePlan,
        *,
        write_authorized: bool,
    ) -> dict[str, Any]:
        if not write_authorized:
            return {
                "ok": True,
                "mode": "OBSERVE",
                "write_authorized": False,
                "entity_id": plan.entity_id,
                "people": len(plan.people),
                "contacts": len(plan.contacts),
                "employments": len(plan.employments),
                "facts": len(plan.facts),
            }

        source_id = self._source_id(plan)
        current_people = self._current_people(plan.entity_id)
        people_ids: dict[str, str] = {}
        for person in plan.people:
            people_ids[person.normalized_name] = self._person_id(
                plan,
                person,
                current_people,
            )

        employment_written = 0
        for row in plan.employments:
            person_id = people_ids.get(
                row.person_normalized_name
            )
            if not person_id:
                raise HunterMaterializerError(
                    "employment person could not be resolved"
                )
            self._employment(
                person_id=person_id,
                row=row,
                observed_at=plan.observed_at,
            )
            employment_written += 1

        contact_inserted = 0
        contact_updated = 0
        for row in plan.contacts:
            person_id = (
                people_ids.get(row.person_normalized_name)
                if row.person_normalized_name
                else None
            )
            _, action = self._contact(
                source_id=source_id,
                person_id=person_id,
                row=row,
                observed_at=plan.observed_at,
            )
            if action == "inserted":
                contact_inserted += 1
            else:
                contact_updated += 1

        facts_inserted = self._facts(
            source_id=source_id,
            plan=plan,
        )
        return {
            "ok": True,
            "mode": "INTERNAL_MATERIALIZE",
            "write_authorized": True,
            "entity_id": plan.entity_id,
            "source_id": source_id,
            "people_resolved": len(people_ids),
            "employments_written": employment_written,
            "contacts_inserted": contact_inserted,
            "contacts_updated": contact_updated,
            "facts_inserted": facts_inserted,
            "outbound_actions": False,
            "payment_actions": False,
            "revenue_actions": False,
        }
