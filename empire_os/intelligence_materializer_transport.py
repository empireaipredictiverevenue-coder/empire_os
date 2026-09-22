"""Least-privilege PostgreSQL writer for Intelligence Fabric materialization."""
from __future__ import annotations

import json
import os
from typing import Any, Callable
from uuid import UUID

from empire_os.intelligence_materializer import (
    PROSPECT_SOURCE_KEY,
    MaterializationPlan,
    build_materialization_plan,
)


ROLE = "empire_intelligence_materializer"


class IntelligenceMaterializerTransportError(RuntimeError):
    """Dedicated materializer transport failed safely."""


def _uuid(value: str, *, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise IntelligenceMaterializerTransportError(
            f"invalid {field}"
        ) from exc


class PostgresIntelligenceMaterializer:
    def __init__(
        self,
        dsn: str,
        *,
        connect_factory: Callable | None = None,
    ) -> None:
        self.dsn = str(dsn or "").strip()
        if not self.dsn:
            raise IntelligenceMaterializerTransportError(
                "EMPIRE_INTELLIGENCE_MATERIALIZER_DSN is required"
            )
        if connect_factory is None:
            try:
                import psycopg
            except ImportError as exc:
                raise IntelligenceMaterializerTransportError(
                    "psycopg is required for materializer transport"
                ) from exc
            connect_factory = psycopg.connect
        self._connect = connect_factory

    @classmethod
    def from_env(cls) -> "PostgresIntelligenceMaterializer":
        return cls(
            os.getenv(
                "EMPIRE_INTELLIGENCE_MATERIALIZER_DSN",
                "",
            )
        )

    @staticmethod
    def _row(cursor) -> dict[str, Any] | None:
        row = cursor.fetchone()
        if row is None:
            return None
        names = [item.name for item in cursor.description]
        return dict(zip(names, row, strict=True))

    @staticmethod
    def _rows(cursor) -> list[dict[str, Any]]:
        names = [item.name for item in cursor.description]
        return [
            dict(zip(names, row, strict=True))
            for row in cursor.fetchall()
        ]

    def _fetch_inputs(
        self,
        cursor,
        prospect_id: str,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        pid = _uuid(prospect_id, field="prospect id")

        cursor.execute(
            """
            SELECT
              id,created_at,business_name,niche,metro,phone,address,
              rating,review_count,runs_ads
            FROM public.prospects
            WHERE id=%s
            LIMIT 1
            """,
            (pid,),
        )
        prospect = self._row(cursor)
        if prospect is None:
            raise IntelligenceMaterializerTransportError(
                "prospect not found"
            )

        cursor.execute(
            """
            SELECT prospect_id,entity_id,match_score,active
            FROM public.prospect_entity_links
            WHERE prospect_id=%s AND active=true
            ORDER BY created_at DESC
            LIMIT 2
            """,
            (pid,),
        )
        links = self._rows(cursor)
        if len(links) != 1:
            raise IntelligenceMaterializerTransportError(
                "prospect must have exactly one active identity link"
            )

        cursor.execute(
            """
            SELECT
              id,prospect_id,score,tier,
              data_completeness_score,business_presence_score,
              market_fit_score,engagement_potential_score,
              enrichment_quality_score,recommended_action,
              scoring_engine,scoring_version,evidence_confidence,
              observed_dimensions,unknown_dimensions,scored_at
            FROM public.prospect_qualifications
            WHERE prospect_id=%s
              AND scoring_engine='empire_os.lead_scoring'
              AND scoring_version IN ('v2','v1')
            ORDER BY
              CASE scoring_version WHEN 'v2' THEN 0 ELSE 1 END,
              scored_at DESC
            LIMIT 1
            """,
            (pid,),
        )
        qualification = self._row(cursor)
        if qualification is None:
            raise IntelligenceMaterializerTransportError(
                "compatible qualification not found"
            )

        return prospect, links[0], qualification

    def _source_id(self, cursor, source_key: str) -> str:
        cursor.execute(
            """
            SELECT id
            FROM public.intelligence_sources
            WHERE source_key=%s
            LIMIT 1
            """,
            (source_key,),
        )
        row = cursor.fetchone()
        if row is None:
            raise IntelligenceMaterializerTransportError(
                "required intelligence source is missing"
            )
        return str(row[0])

    def _apply_plan(
        self,
        cursor,
        plan: MaterializationPlan,
    ) -> dict[str, Any]:
        prospect_source_id = self._source_id(
            cursor,
            PROSPECT_SOURCE_KEY,
        )

        facts_inserted = 0
        facts_existing = 0
        for fact in plan.fact_rows:
            if fact.source_key != PROSPECT_SOURCE_KEY:
                raise IntelligenceMaterializerTransportError(
                    "unexpected fact source"
                )
            cursor.execute(
                """
                INSERT INTO public.intelligence_facts(
                  entity_type,entity_id,fact_key,fact_value,
                  source_id,confidence,first_seen_at,last_seen_at,
                  evidence_hash
                )
                VALUES(
                  'company',%s,%s,%s::jsonb,
                  %s,%s,%s,%s,%s
                )
                ON CONFLICT (evidence_hash)
                WHERE evidence_hash IS NOT NULL
                DO NOTHING
                RETURNING id
                """,
                (
                    plan.entity_id,
                    fact.fact_key,
                    json.dumps(fact.fact_value, sort_keys=True),
                    prospect_source_id,
                    fact.confidence,
                    fact.first_seen_at,
                    fact.last_seen_at,
                    fact.evidence_hash,
                ),
            )
            if cursor.fetchone() is None:
                facts_existing += 1
            else:
                facts_inserted += 1

        scores_inserted = 0
        scores_existing = 0
        for score in plan.score_rows:
            cursor.execute(
                """
                INSERT INTO public.intelligence_scores(
                  entity_type,entity_id,score_type,score,confidence,
                  model_key,features,explanation,scored_at
                )
                VALUES(
                  'company',%s,%s,%s,%s,
                  %s,%s::jsonb,%s::jsonb,%s
                )
                ON CONFLICT(
                  entity_type,entity_id,score_type,model_key,scored_at
                )
                DO NOTHING
                RETURNING id
                """,
                (
                    plan.entity_id,
                    score.score_type,
                    score.score,
                    score.confidence,
                    score.model_key,
                    json.dumps(score.features, sort_keys=True),
                    json.dumps(score.explanation, sort_keys=True),
                    score.scored_at,
                ),
            )
            if cursor.fetchone() is None:
                scores_existing += 1
            else:
                scores_inserted += 1

        return {
            "prospect_id": plan.prospect_id,
            "entity_id": plan.entity_id,
            "facts_inserted": facts_inserted,
            "facts_existing": facts_existing,
            "scores_inserted": scores_inserted,
            "scores_existing": scores_existing,
            "skipped_fields": list(plan.skipped_fields),
        }

    def materialize(self, prospect_id: str) -> dict[str, Any]:
        pid = _uuid(prospect_id, field="prospect id")
        try:
            with self._connect(self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SET LOCAL ROLE " + ROLE)
                    prospect, link, qualification = (
                        self._fetch_inputs(cursor, pid)
                    )
                    plan = build_materialization_plan(
                        prospect=prospect,
                        identity_link=link,
                        qualification=qualification,
                    )
                    return self._apply_plan(cursor, plan)
        except IntelligenceMaterializerTransportError:
            raise
        except Exception as exc:
            raise IntelligenceMaterializerTransportError(
                "dedicated Intelligence materializer failed"
            ) from exc


COMPETITOR_AUDIENCE_SOURCE_KEY = "empire.competitor_audience.public.v1"


def _competitor_evidence_refs(payload: dict[str, Any]) -> tuple[str, ...]:
    evidence = payload.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise IntelligenceMaterializerTransportError(
            "competitor audience evidence is required"
        )

    refs = []
    for item in evidence:
        if not isinstance(item, dict):
            raise IntelligenceMaterializerTransportError(
                "invalid competitor audience evidence"
            )
        ref = str(item.get("source_ref") or "").strip()
        if not ref:
            raise IntelligenceMaterializerTransportError(
                "competitor audience source_ref is required"
            )
        refs.append(ref)

    return tuple(sorted(set(refs)))


def _competitor_evidence_fingerprints(
    payload: dict[str, Any],
) -> tuple[str, ...]:
    """Stable evidence identity across repeated sweeps.

    observed_at is deliberately excluded so revisiting the same public source
    does not create a duplicate signal. competitor_key and evidence_type stay
    in the fingerprint so separate relationships found on one page remain
    distinct evidence.
    """
    evidence = payload.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise IntelligenceMaterializerTransportError(
            "competitor audience evidence is required"
        )

    fingerprints = []
    for item in evidence:
        if not isinstance(item, dict):
            raise IntelligenceMaterializerTransportError(
                "invalid competitor audience evidence"
            )

        source_ref = str(item.get("source_ref") or "").strip()
        competitor_key = str(item.get("competitor_key") or "").strip()
        evidence_type = str(item.get("evidence_type") or "").strip()

        if not source_ref:
            raise IntelligenceMaterializerTransportError(
                "competitor audience source_ref is required"
            )
        if not competitor_key:
            raise IntelligenceMaterializerTransportError(
                "competitor audience competitor_key is required"
            )
        if not evidence_type:
            raise IntelligenceMaterializerTransportError(
                "competitor audience evidence_type is required"
            )

        fingerprints.append(
            "|".join((competitor_key, evidence_type, source_ref))
        )

    return tuple(sorted(set(fingerprints)))


def persist_competitor_audience_signal(
    writer: PostgresIntelligenceMaterializer,
    signal: dict[str, Any],
) -> dict[str, Any]:
    """Persist one resolved competitor-audience signal safely.

    This writes Intelligence Fabric evidence only. It cannot create prospects,
    infer buyer intent, enable outreach, or grant execution authority.
    """
    if signal.get("signal_type") != "competitor_audience_evidence":
        raise IntelligenceMaterializerTransportError(
            "unexpected competitor signal type"
        )
    if signal.get("signal_domain") != "competitive_intelligence":
        raise IntelligenceMaterializerTransportError(
            "unexpected competitor signal domain"
        )
    if signal.get("execution_authority") != "none":
        raise IntelligenceMaterializerTransportError(
            "competitor signal has execution authority"
        )
    if signal.get("outreach_enabled") is not False:
        raise IntelligenceMaterializerTransportError(
            "competitor signal cannot enable outreach"
        )
    if signal.get("buyer_intent_inferred") is not False:
        raise IntelligenceMaterializerTransportError(
            "competitor signal cannot infer buyer intent"
        )
    if signal.get("commercial_intent_inferred") is not False:
        raise IntelligenceMaterializerTransportError(
            "competitor signal cannot infer commercial intent"
        )

    entity_id = _uuid(signal.get("entity_id"), field="entity id")
    observed_at = str(signal.get("observed_at") or "").strip()
    if not observed_at:
        raise IntelligenceMaterializerTransportError(
            "observed_at is required"
        )

    try:
        strength = float(signal.get("strength"))
        confidence = float(signal.get("confidence"))
    except (TypeError, ValueError) as exc:
        raise IntelligenceMaterializerTransportError(
            "invalid competitor signal confidence"
        ) from exc

    if not 0.0 <= strength <= 1.0:
        raise IntelligenceMaterializerTransportError(
            "strength must be between 0 and 1"
        )
    if not 0.0 <= confidence <= 1.0:
        raise IntelligenceMaterializerTransportError(
            "confidence must be between 0 and 1"
        )

    payload = signal.get("payload")
    if not isinstance(payload, dict):
        raise IntelligenceMaterializerTransportError(
            "competitor signal payload is required"
        )

    evidence_refs = _competitor_evidence_refs(payload)
    evidence_fingerprints = _competitor_evidence_fingerprints(payload)

    try:
        with writer._connect(writer.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL ROLE {ROLE}")

                source_id = writer._source_id(
                    cursor,
                    COMPETITOR_AUDIENCE_SOURCE_KEY,
                )

                supplied_source_id = _uuid(
                    signal.get("source_id"),
                    field="source id",
                )
                if supplied_source_id != _uuid(
                    source_id,
                    field="canonical source id",
                ):
                    raise IntelligenceMaterializerTransportError(
                        "competitor signal source mismatch"
                    )

                cursor.execute(
                    """
                    SELECT payload
                    FROM public.intelligence_signals
                    WHERE entity_id=%s
                      AND signal_type='competitor_audience_evidence'
                      AND signal_domain='competitive_intelligence'
                      AND source_id=%s
                    """,
                    (entity_id, source_id),
                )

                for row in cursor.fetchall():
                    existing_payload = row[0]
                    if isinstance(existing_payload, str):
                        existing_payload = json.loads(existing_payload)
                    if not isinstance(existing_payload, dict):
                        continue
                    try:
                        existing_fingerprints = (
                            _competitor_evidence_fingerprints(
                                existing_payload
                            )
                        )
                    except IntelligenceMaterializerTransportError:
                        continue
                    if existing_fingerprints == evidence_fingerprints:
                        return {
                            "entity_id": entity_id,
                            "signal_type": "competitor_audience_evidence",
                            "inserted": False,
                            "existing": True,
                            "evidence_refs": list(evidence_refs),
                            "execution_authority": "none",
                        }

                cursor.execute(
                    """
                    INSERT INTO public.intelligence_signals(
                      entity_id,signal_type,signal_domain,observed_at,
                      source_id,strength,confidence,payload
                    )
                    VALUES(
                      %s,'competitor_audience_evidence',
                      'competitive_intelligence',%s,%s,%s,%s,%s::jsonb
                    )
                    RETURNING id
                    """,
                    (
                        entity_id,
                        observed_at,
                        source_id,
                        strength,
                        confidence,
                        json.dumps(payload, sort_keys=True),
                    ),
                )
                row = cursor.fetchone()
                if row is None:
                    raise IntelligenceMaterializerTransportError(
                        "competitor signal insert failed"
                    )

                return {
                    "id": str(row[0]),
                    "entity_id": entity_id,
                    "signal_type": "competitor_audience_evidence",
                    "inserted": True,
                    "existing": False,
                    "evidence_refs": list(evidence_refs),
                    "execution_authority": "none",
                }

    except IntelligenceMaterializerTransportError:
        raise
    except Exception as exc:
        raise IntelligenceMaterializerTransportError(
            "competitor audience signal persistence failed"
        ) from exc
