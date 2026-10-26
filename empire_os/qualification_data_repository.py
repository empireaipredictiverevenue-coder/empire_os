"""Canonical data repository for qualification worker v2."""
from __future__ import annotations

from typing import Any

from empire_os.canonical_data_gateway import CanonicalDataGateway
from empire_os.data_query import ConflictAction, DataFilter, OrderSpec
from empire_os.data_values import JsonValue


PROSPECT_COLUMNS = ",".join((
    "id",
    "created_at",
    "business_name",
    "niche",
    "metro",
    "phone",
    "website",
    "address",
    "rating",
    "review_count",
    "buy_signal_score",
    "runs_ads",
    "status",
    "notes",
    "contact_name",
    "contact_title",
    "contact_source",
))


class QualificationDataRepository:
    def __init__(self, gateway: CanonicalDataGateway) -> None:
        self._gateway = gateway

    def fetch_prospect(
        self,
        prospect_id: str,
    ) -> dict[str, Any]:
        rows = self._gateway.query(
            "prospects",
            PROSPECT_COLUMNS,
            filters=(DataFilter.eq("id", str(prospect_id)),),
            limit=2,
        )
        if len(rows) != 1:
            raise RuntimeError(
                f"prospect not found or ambiguous: {prospect_id}"
            )
        return dict(rows[0])

    def fetch_pending_prospects(
        self,
        *,
        limit: int,
        scoring_engine: str,
        scoring_version: str,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 25))
        prospects = self._gateway.query(
            "prospects",
            PROSPECT_COLUMNS,
            order=(OrderSpec("created_at", descending=True),),
            limit=limit * 4,
        )
        if not prospects:
            return []

        ids = tuple(
            str(row["id"])
            for row in prospects
            if row.get("id")
        )
        if not ids:
            return []

        existing = self._gateway.query(
            "prospect_qualifications",
            "prospect_id",
            filters=(
                DataFilter.eq("scoring_engine", scoring_engine),
                DataFilter.eq("scoring_version", scoring_version),
                DataFilter.in_("prospect_id", ids),
            ),
            limit=max(1, len(ids)),
        )
        done = {
            str(row.get("prospect_id"))
            for row in existing
            if row.get("prospect_id")
        }
        return [
            row
            for row in prospects
            if str(row.get("id")) not in done
        ][:limit]

    def fetch_historical_pending_page(
        self,
        *,
        offset: int,
        limit: int,
        scoring_engine: str,
        scoring_version: str,
    ) -> dict[str, Any]:
        """Bounded archival backfill selection, ordered oldest to newest.

        Returns an advancing offset through canonical prospects. Scored rows
        count as scanned but are not requalified. If the quota fills inside
        a page, the next cursor stops directly after the final candidate,
        preserving all unvisited records for the next cycle.
        """
        if type(offset) is not int or not 0 <= offset <= 1_000_000:
            raise ValueError("historical backfill offset out of bounds")
        if type(limit) is not int or not 1 <= limit <= 25:
            raise ValueError("historical backfill limit must be 1-25")
        page_size = min(100, max(25, limit * 4))
        prospects = self._gateway.query(
            "prospects",
            PROSPECT_COLUMNS,
            order=(
                OrderSpec("created_at", descending=False),
                OrderSpec("id", descending=False),
            ),
            limit=page_size,
            offset=offset,
        )
        ids = [str(p.get("id") or "").strip() for p in prospects]
        if not all(ids) or len(set(ids)) != len(ids):
            raise ValueError("historical backfill duplicate/empty prospect ids")
        done: set[str] = set()
        if ids:
            existing = self._gateway.query(
                "prospect_qualifications",
                "prospect_id",
                filters=(
                    DataFilter.eq("scoring_engine", scoring_engine),
                    DataFilter.eq("scoring_version", scoring_version),
                    DataFilter.in_("prospect_id", tuple(ids)),
                ),
                limit=len(ids),
            )
            done = {
                str(row.get("prospect_id") or "").strip()
                for row in existing if row.get("prospect_id")
            }
            if not done <= set(ids):
                raise ValueError("historical backfill qualification mismatch")
        selected: list[dict[str, Any]] = []
        consumed = 0
        for row in prospects:
            consumed += 1
            if str(row["id"]) not in done:
                selected.append(dict(row))
                if len(selected) == limit:
                    break
        end_of_archive = consumed == len(prospects) and len(prospects) < page_size
        return {
            "candidate_rows": selected,
            "scanned_rows": consumed,
            "next_offset": offset + consumed,
            "archive_exhausted": end_of_archive,
            "source": "canonical_empiredb_prospects",
            "no_send_authority": True,
        }

    def fetch_historical_identity_linked_page(
        self,
        *,
        offset: int,
        limit: int,
        scoring_engine: str,
        scoring_version: str,
    ) -> dict[str, Any]:
        """Bounded existing-linked unscored prospects, without creating identities.

        Cursor is over already-linked canonical source rows, not a second
        prospect population. This lets v2 scoring reach formerly stranded
        records whose identity proof already exists.
        """
        if type(offset) is not int or not 0 <= offset <= 1_000_000:
            raise ValueError("historical identity backfill offset out of bounds")
        if type(limit) is not int or not 1 <= limit <= 25:
            raise ValueError("historical identity backfill limit must be 1-25")
        page_size = min(100, max(25, limit * 4))
        links = self._gateway.query(
            "prospect_entity_links",
            "id,prospect_id,entity_id,active,created_at",
            filters=(DataFilter.eq("active", True),),
            order=(
                OrderSpec("created_at", descending=False),
                OrderSpec("id", descending=False),
            ),
            limit=page_size,
            offset=offset,
        )
        ids = [str(link.get("prospect_id") or "").strip() for link in links]
        if not all(ids) or len(set(ids)) != len(ids):
            raise ValueError("ambiguous or duplicate active identity links")
        done: set[str] = set()
        if ids:
            existing = self._gateway.query(
                "prospect_qualifications",
                "prospect_id",
                filters=(
                    DataFilter.eq("scoring_engine", scoring_engine),
                    DataFilter.eq("scoring_version", scoring_version),
                    DataFilter.in_("prospect_id", tuple(ids)),
                ),
                limit=len(ids),
            )
            done = {
                str(row.get("prospect_id") or "").strip()
                for row in existing if row.get("prospect_id")
            }
            if not done <= set(ids):
                raise ValueError("unexpected qualification outside linked page")
        candidates = []
        scanned = 0
        for link in links:
            scanned += 1
            pid = str(link["prospect_id"])
            if pid not in done:
                candidates.append(pid)
                if len(candidates) == limit:
                    break
        rows = []
        if candidates:
            records = self._gateway.query(
                "prospects",
                PROSPECT_COLUMNS,
                filters=(DataFilter.in_("id", tuple(candidates)),),
                limit=len(candidates),
            )
            by_id = {str(item.get("id") or ""): dict(item) for item in records}
            if len(by_id) != len(candidates) or not set(candidates) <= set(by_id):
                raise ValueError("linked canonical prospect missing")
            rows = [by_id[pid] for pid in candidates]
        return {
            "candidate_rows": rows,
            "scanned_rows": scanned,
            "next_offset": offset + scanned,
            "archive_exhausted": len(links) < page_size and scanned == len(links),
            "source": "canonical_empiredb_prospect_entity_links",
            "no_send_authority": True,
        }

    def fetch_unlinked_allocatable_prospects(
        self,
        *,
        limit: int,
        scoring_engine: str,
        scoring_version: str,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 25))
        qualifications = self._gateway.query(
            "prospect_qualifications",
            "prospect_id,scored_at,result_payload",
            filters=(
                DataFilter.eq("scoring_engine", scoring_engine),
                DataFilter.eq("scoring_version", scoring_version),
                DataFilter.eq("status", "scored"),
                DataFilter.in_("tier", ("hot", "warm")),
                DataFilter.is_null("entity_id"),
            ),
            order=(OrderSpec("scored_at", descending=True),),
            limit=limit * 5,
        )

        ids: list[str] = []
        for row in qualifications:
            prospect_id = str(row.get("prospect_id") or "").strip()
            if not prospect_id:
                continue
            result_payload = row.get("result_payload")
            identity_state = (
                result_payload.get("identity_resolution")
                if isinstance(result_payload, dict)
                else None
            )
            if (
                isinstance(identity_state, dict)
                and identity_state.get("attempted") is True
            ):
                continue
            ids.append(prospect_id)
            if len(ids) >= limit:
                break

        if not ids:
            return []

        prospects = self._gateway.query(
            "prospects",
            PROSPECT_COLUMNS,
            filters=(DataFilter.in_("id", ids),),
            limit=len(ids),
        )
        by_id = {
            str(row.get("id")): row
            for row in prospects
            if row.get("id")
        }
        return [
            by_id[prospect_id]
            for prospect_id in ids
            if prospect_id in by_id
        ]

    def fetch_low_confidence_recovery_candidates(
        self,
        *,
        limit: int,
        scoring_engine: str,
        scoring_version: str,
        confidence_floor: float,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 25))
        rows = self._gateway.query(
            "prospect_qualifications",
            (
                "id,prospect_id,entity_id,status,evidence_confidence,"
                "observed_dimensions,unknown_dimensions,result_payload,scored_at"
            ),
            filters=(
                DataFilter.eq("scoring_engine", scoring_engine),
                DataFilter.eq("scoring_version", scoring_version),
                DataFilter.eq("status", "insufficient_evidence"),
            ),
            order=(
                OrderSpec("evidence_confidence", descending=True, nulls_last=True),
                OrderSpec("scored_at", descending=True, nulls_last=True),
                OrderSpec("prospect_id", descending=False),
            ),
            limit=limit * 5,
        )
        selected: list[dict[str, Any]] = []
        for row in rows:
            try:
                confidence = float(row.get("evidence_confidence") or 0.0)
            except (TypeError, ValueError):
                confidence = 0.0
            if confidence >= float(confidence_floor):
                continue
            selected.append(dict(row))
            if len(selected) >= limit:
                break
        return selected

    def record_recovery_metadata(
        self,
        qualification_id: str,
        result_payload: dict[str, Any],
        *,
        updated_at: str,
    ) -> dict[str, Any]:
        rows = self._gateway.update(
            "prospect_qualifications",
            {"id": str(qualification_id)},
            {
                "result_payload": JsonValue(result_payload),
                "updated_at": updated_at,
            },
        )
        if len(rows) != 1:
            raise RuntimeError("qualification recovery metadata update failed")
        return dict(rows[0])

    def fetch_latest_acquisition(
        self,
        prospect_id: str,
    ) -> dict[str, Any] | None:
        rows = self._gateway.query(
            "prospect_acquisitions",
            "prospect_id,source,source_url,evidence,created_at",
            filters=(DataFilter.eq("prospect_id", prospect_id),),
            order=(OrderSpec("created_at", descending=True),),
            limit=1,
        )
        return dict(rows[0]) if rows else None

    def fetch_active_identity_link(
        self,
        prospect_id: str,
    ) -> dict[str, Any] | None:
        rows = self._gateway.query(
            "prospect_entity_links",
            "prospect_id,entity_id,match_method,match_score,active,created_at",
            filters=(
                DataFilter.eq("prospect_id", prospect_id),
                DataFilter.eq("active", True),
            ),
            order=(OrderSpec("created_at", descending=True),),
            limit=2,
        )
        if len(rows) > 1:
            raise RuntimeError("multiple active identity links")
        return dict(rows[0]) if rows else None

    def insert_identity_entity(
        self,
        payload: dict[str, Any],
    ) -> None:
        self._gateway.insert_ignore_conflicts(
            "business_entities",
            payload,
            conflict_columns=("id",),
            return_repr=False,
        )

    def insert_identity_link(
        self,
        payload: dict[str, Any],
    ) -> None:
        self._gateway.insert_ignore_conflicts(
            "prospect_entity_links",
            payload,
            conflict_columns=("prospect_id",),
            return_repr=False,
        )

    def promote_verified_website(
        self,
        prospect_id: str,
        website: str,
    ) -> str:
        rows = self._gateway.update(
            "prospects",
            {"id": prospect_id},
            {"website": website},
        )
        if not rows:
            raise RuntimeError("verified website promotion returned no row")

        verified = self._gateway.query(
            "prospects",
            "id,website",
            filters=(DataFilter.eq("id", prospect_id),),
            limit=1,
        )
        if (
            not verified
            or str(verified[0].get("website") or "").strip() != website
        ):
            raise RuntimeError("verified website promotion did not persist")
        return website

    def upsert_qualification(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        prepared = dict(payload)
        for field in ("observed_dimensions", "unknown_dimensions"):
            if field in prepared:
                prepared[field] = JsonValue(prepared[field])

        rows = self._gateway.upsert(
            "prospect_qualifications",
            prepared,
            conflict_columns=(
                "prospect_id",
                "scoring_engine",
                "scoring_version",
            ),
            action=ConflictAction.MERGE,
            return_repr=True,
        )
        if not rows:
            raise RuntimeError("qualification upsert returned no row")
        return dict(rows[0])

    def snapshot(self) -> dict[str, object]:
        backend = self._gateway.snapshot().as_dict()
        return {
            "backend": backend["primary_backend"],
            "configured": backend["configured"],
            "dual_write_enabled": backend["dual_write_enabled"],
            "write_fallback_enabled": backend["write_fallback_enabled"],
        }
