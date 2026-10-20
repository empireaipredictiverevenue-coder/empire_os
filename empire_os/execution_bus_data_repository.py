"""Canonical data repository for the autonomous execution bus.

This repository owns data access semantics only. It does not decide whether a
job should execute, widen approval authority, or change execution mode.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping

from empire_os.buyer_allocation_repository import BuyerAllocationDataRepository
from empire_os.canonical_data_gateway import CanonicalDataGateway
from empire_os.commercial_event_repository import CommercialEventRepository
from empire_os.data_query import DataFilter, OrderSpec
from empire_os.data_values import unwrap_data_value


PROSPECT_COLUMNS = (
    "id,business_name,niche,metro,status,buy_signal_score,phone,website,address,"
    "rating,review_count,contact_name,contact_title,contact_source,contacted_status"
)

ALLOCATION_PROSPECT_COLUMNS = (
    "id,business_name,niche,metro,status,buy_signal_score,"
    "phone,website,address,contact_source,contacted_status"
)

BUYER_CAPACITY_COLUMNS = (
    "id,buyer_name,niche,metro,is_active,status,"
    "daily_cap,calls_today,destination_phone,webhook_url,"
    "reviewed_at,commercial_activation_state,"
    "commercial_activated_at,commercial_terms_source,"
    "commercial_terms_reference,commercial_terms_verified_at,"
    "capacity_verified_at,delivery_verified_at"
)


class ExecutionBusDataRepository:
    def __init__(self, gateway: CanonicalDataGateway) -> None:
        self._gateway = gateway
        self.events = CommercialEventRepository(gateway)
        self.buyer_allocation = BuyerAllocationDataRepository(gateway)

    def rpc(
        self,
        name: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._gateway.rpc(name, payload)

    def append_commercial_event(
        self,
        event: dict[str, Any],
    ) -> bool:
        return self.events.append_idempotent(event)

    def ingest_prospect_atomic(
        self,
        *,
        prospect: dict[str, Any],
        evidence: dict[str, Any],
        ingest_key: str,
        identity_keys: list[str],
    ) -> Any:
        return self.rpc(
            "ingest_prospect_atomic",
            {
                "p_prospect": prospect,
                "p_evidence": evidence,
                "p_ingest_key": ingest_key,
                "p_identity_keys": identity_keys,
            },
        )

    def qualification_candidates(
        self,
        *,
        aliases: Iterable[str],
        metro: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        values = tuple(str(alias) for alias in aliases if str(alias))
        if not values:
            return []
        return self._gateway.query(
            "prospects",
            PROSPECT_COLUMNS,
            filters=(
                DataFilter.in_("niche", values),
                DataFilter.ilike("metro", metro),
                DataFilter.ne("status", "archived"),
            ),
            order=(
                OrderSpec(
                    "buy_signal_score",
                    descending=True,
                    nulls_last=True,
                ),
                OrderSpec("created_at"),
            ),
            limit=limit,
        )

    def existing_qualification_ids(
        self,
        prospect_ids: Iterable[str],
        *,
        scoring_engine: str,
        scoring_version: str,
    ) -> set[str]:
        ids = tuple(str(value) for value in prospect_ids if str(value))
        if not ids:
            return set()
        rows = self._gateway.query(
            "prospect_qualifications",
            "prospect_id",
            filters=(
                DataFilter.in_("prospect_id", ids),
                DataFilter.eq("scoring_engine", scoring_engine),
                DataFilter.eq("scoring_version", scoring_version),
            ),
            limit=max(1, len(ids)),
        )
        return {
            str(row.get("prospect_id"))
            for row in rows
            if row.get("prospect_id")
        }

    def allocation_qualifications(
        self,
        prospect_ids: Iterable[str],
    ) -> list[dict[str, Any]]:
        ids = tuple(str(value) for value in prospect_ids if str(value))
        if not ids:
            return []
        return self._gateway.query(
            "prospect_qualifications",
            "prospect_id,score,tier,status,scored_at",
            filters=(
                DataFilter.in_("prospect_id", ids),
                DataFilter.eq("status", "scored"),
                DataFilter.in_("tier", ("hot", "warm")),
                DataFilter.gte("score", 50),
                DataFilter.eq("scoring_engine", "empire_os.lead_scoring"),
                DataFilter.eq("scoring_version", "v1"),
            ),
            order=(
                OrderSpec("score", descending=True),
                OrderSpec("scored_at"),
            ),
            limit=max(1, len(ids)),
        )

    def active_fulfilment_prospect_ids(
        self,
        prospect_ids: Iterable[str],
    ) -> set[str]:
        ids = tuple(str(value) for value in prospect_ids if str(value))
        if not ids:
            return set()
        rows = self._gateway.query(
            "fulfilment_orders",
            "prospect_id",
            filters=(
                DataFilter.in_("prospect_id", ids),
                DataFilter.not_in("state", ("rejected", "cancelled")),
            ),
            limit=max(1, len(ids)),
        )
        return {
            str(row.get("prospect_id"))
            for row in rows
            if row.get("prospect_id")
        }

    def find_gtm_job(
        self,
        idempotency_key: str,
    ) -> dict[str, Any] | None:
        rows = self._gateway.query(
            "gtm_jobs",
            "id",
            filters=(DataFilter.eq("idempotency_key", idempotency_key),),
            limit=1,
        )
        return dict(rows[0]) if rows else None

    def ensure_gtm_job(
        self,
        row: dict[str, Any],
    ) -> tuple[dict[str, Any], bool]:
        idempotency_key = str(row.get("idempotency_key") or "").strip()
        if not idempotency_key:
            raise ValueError("gtm job idempotency_key is required")

        existing = self.find_gtm_job(idempotency_key)
        if existing is not None:
            return existing, False

        try:
            rows = self._gateway.insert(
                "gtm_jobs",
                row,
                return_repr=True,
            )
        except Exception:
            existing = self.find_gtm_job(idempotency_key)
            if existing is not None:
                return existing, False
            raise

        if not rows:
            raise RuntimeError("gtm job insert returned no row")
        return dict(rows[0]), True

    def prospect_by_id(
        self,
        prospect_id: str,
    ) -> dict[str, Any] | None:
        rows = self._gateway.query(
            "prospects",
            ALLOCATION_PROSPECT_COLUMNS,
            filters=(DataFilter.eq("id", prospect_id),),
            limit=1,
        )
        if not rows:
            return None
        if len(rows) != 1:
            raise RuntimeError("prospect query returned multiple rows")
        return dict(rows[0])

    def allocation_market_prospects(
        self,
        *,
        aliases: Iterable[str],
        metro: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        values = tuple(str(alias) for alias in aliases if str(alias))
        if not values:
            return []
        return self._gateway.query(
            "prospects",
            ALLOCATION_PROSPECT_COLUMNS,
            filters=(
                DataFilter.in_("niche", values),
                DataFilter.ilike("metro", metro),
                DataFilter.ne("status", "archived"),
            ),
            order=(
                OrderSpec(
                    "buy_signal_score",
                    descending=True,
                    nulls_last=True,
                ),
                OrderSpec("created_at"),
            ),
            limit=limit,
        )

    def capacity_buyer_page(
        self,
        *,
        page_size: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        return self._gateway.query(
            "buyers",
            BUYER_CAPACITY_COLUMNS,
            limit=page_size,
            offset=offset,
        )

    def inventory_prospects(
        self,
        *,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return self._gateway.query(
            "prospects",
            PROSPECT_COLUMNS,
            filters=(DataFilter.ne("status", "archived"),),
            order=(
                OrderSpec("buy_signal_score", descending=True, nulls_last=True),
                OrderSpec("created_at", descending=True),
            ),
            limit=max(1, int(limit)),
        )

    def prospect_conversation_events(
        self,
        prospect_id: str,
        *,
        conversation_limit: int = 20,
        event_limit: int = 200,
    ) -> list[dict[str, Any]]:
        conversations = self._gateway.query(
            "empire_conversations",
            "id,channel,state,updated_at",
            filters=(DataFilter.eq("prospect_id", prospect_id),),
            order=(OrderSpec("updated_at", descending=True),),
            limit=max(1, int(conversation_limit)),
        )
        by_id = {
            str(row.get("id")): str(row.get("channel") or "")
            for row in conversations
            if row.get("id")
        }
        if not by_id:
            return []
        rows = self._gateway.query(
            "empire_conversation_events",
            "conversation_id,event_type,direction,provider_event_id,evidence,occurred_at",
            filters=(DataFilter.in_("conversation_id", tuple(by_id)),),
            order=(OrderSpec("occurred_at", descending=True),),
            limit=max(1, int(event_limit)),
        )
        return [
            {**row, "channel": by_id.get(str(row.get("conversation_id")), "")}
            for row in rows
        ]

    def prospect_commercial_outcomes(
        self,
        prospect_id: str,
        *,
        order_limit: int = 20,
        outcome_limit: int = 100,
    ) -> list[dict[str, Any]]:
        orders = self._gateway.query(
            "fulfilment_orders",
            "id",
            filters=(DataFilter.eq("prospect_id", prospect_id),),
            order=(OrderSpec("updated_at", descending=True),),
            limit=max(1, int(order_limit)),
        )
        order_ids = tuple(
            str(row.get("id"))
            for row in orders
            if row.get("id")
        )
        if not order_ids:
            return []
        return self._gateway.query(
            "commercial_outcomes",
            "id,fulfilment_order_id,delivery_outcome,conversion_outcome,"
            "evidence_kind,evidence_reference,evidence,recorded_at",
            filters=(DataFilter.in_("fulfilment_order_id", order_ids),),
            order=(OrderSpec("recorded_at", descending=True),),
            limit=max(1, int(outcome_limit)),
        )

    def verified_outcome_feedback(self, fulfilment_order_id: str, *, tenant_id: str,
                                 repo_root, as_of) -> dict[str, Any]:
        """Read full canonical evidence through existing privileges; no projection trust."""
        from decimal import Decimal
        from empire_os.department_work_queue import DepartmentWorkQueue
        from empire_os.outcome_feedback import build_verified_feedback_from_records
        if self._gateway.snapshot().as_dict().get("primary_backend") != "empiredb":
            raise ValueError("canonical EmpireDB required for verified outcome handoff")

        def one(table, filters):
            rows = self._gateway.query(table, "*", filters=filters, limit=2)
            if len(rows) != 1:
                raise ValueError(f"unique canonical {table} evidence required")
            return unwrap_data_value(rows[0])

        order = one("fulfilment_orders", (DataFilter.eq("id", fulfilment_order_id),))
        buyer = one("buyers", (DataFilter.eq("id", order.get("buyer_id")),))
        if not tenant_id or buyer.get("org_id") != tenant_id:
            raise ValueError("canonical order tenant mismatch or missing")
        outcomes = self._gateway.query("commercial_outcomes", "*",
            filters=(DataFilter.eq("fulfilment_order_id", fulfilment_order_id),),
            order=(OrderSpec("recorded_at", descending=True), OrderSpec("id", descending=True)), limit=1)
        if len(outcomes) != 1:
            raise ValueError("independently recorded canonical outcome required")
        outcome = unwrap_data_value(outcomes[0])
        events = self._gateway.query("commercial_events", "*",
            filters=(DataFilter.eq("idempotency_key", f"revenue:{fulfilment_order_id}:v1"),), limit=2)
        if len(events) > 1:
            raise ValueError("ambiguous recognized revenue event")
        event = unwrap_data_value(events[0]) if events else None
        payments = []
        if event is not None:
            payload = event.get("payload") or {}
            request = one("bsc_payment_requests", (DataFilter.eq("id", payload.get("payment_request_id")),))
            if (request.get("tenant_id") not in (None, tenant_id)
                    or request.get("fulfilment_order_id") != fulfilment_order_id or request.get("status") != "approved"
                    or not request.get("approved_at") or not request.get("approved_by")
                    or not request.get("commercial_terms_sha256")
                    or request["commercial_terms_sha256"] != (order.get("commercial_payload") or {}).get("commercial_terms_sha256")
                    or Decimal(str(request.get("amount_usdt"))) * 100 != order.get("price_cents")):
                raise ValueError("canonical approved payment request mismatch")
            from datetime import datetime
            approved_at = datetime.fromisoformat(str(request["approved_at"]).replace("Z", "+00:00"))
            limit = datetime.fromisoformat(as_of.replace("Z", "+00:00")) if isinstance(as_of, str) else as_of
            if approved_at.tzinfo is None or approved_at > limit:
                raise ValueError("future payment approval evidence")
            if payload.get("settlement_source") == "direct_payment" and request.get("settlement_mode") == "direct":
                proof = one("bsc_payment_evidence", (DataFilter.eq("id", payload.get("evidence_id")),))
                if proof.get("request_id") != request["id"]:
                    raise ValueError("canonical payment request linkage mismatch")
                table = "bsc_payment_evidence"
            elif payload.get("settlement_source") == "escrow_release" and request.get("settlement_mode") == "escrow":
                agreement = one("bsc_escrow_agreements", (DataFilter.eq("request_id", request["id"]),))
                proof = one("bsc_escrow_evidence", (DataFilter.eq("id", payload.get("evidence_id")),))
                if (agreement.get("status") != "released" or proof.get("agreement_id") != agreement.get("id")
                        or proof.get("action") != "released"):
                    raise ValueError("canonical escrow release linkage mismatch")
                table = "bsc_escrow_evidence"
            else:
                raise ValueError("canonical settlement mode mismatch")
            if (proof.get("tenant_id") not in (None, tenant_id)
                    or proof.get("synthetic") is True or proof.get("forecast_derived") is True or proof.get("verified") is False):
                raise ValueError("unverified payment evidence")
            payments = [{**proof, "tenant_id": tenant_id, "fulfilment_order_id": fulfilment_order_id,
                         "canonical_evidence_ref": f"canonical:{table}:{proof['id']}"}]
        causal = (order.get("commercial_payload") or {}).get("causal_lineage")
        work = None
        if causal is not None:
            execution_ref = causal.get("execution_ref")
            task_key = causal.get("task_key")
            if not task_key or execution_ref is not None and execution_ref != f"department_work:{task_key}":
                raise ValueError("scoped causal handoff requires explicit canonical work")
            work = DepartmentWorkQueue.read_completed_work(repo_root, task_key)
        return build_verified_feedback_from_records(order=order, outcome=outcome, payment_evidence=payments,
            revenue_event=event, tenant_id=tenant_id, as_of=as_of, canonical_work=work)

    def _outreach_canonical_linkage(self, record: Mapping[str, Any], *, repo_root,
                                    as_of: datetime, require_order: bool = True) -> dict[str, Any]:
        """Attach existing verified feedback only over explicit canonical case/order FKs.

        Input adaptive metadata is checked against the canonical intent, never used
        to discover orders. Names, addresses, copy and timing are not join keys.
        """
        from empire_os.decision_identity import validate_causal_lineage
        from empire_os.outcome_feedback import validate_verified_feedback

        if self._gateway.snapshot().as_dict().get("primary_backend") != "empiredb":
            raise ValueError("canonical EmpireDB required for outreach outcome bridge")
        if as_of.tzinfo is None:
            raise ValueError("timezone-aware outreach snapshot required")
        raw = unwrap_data_value(dict(record))
        # The producer owns enrichment; do not retain caller-provided feedback.
        raw.pop("verified_outcome_feedback", None)
        raw.pop("outreach_outcome_attribution", None)
        raw.pop("qualified_conversation_evidence", None)
        raw.pop("commercial_terms_evidence", None)
        intent_id = raw.get("intent_id")
        if not intent_id or raw.get("outbound_intent_id", intent_id) != intent_id:
            raise ValueError("outbound intent mismatch or missing")

        def rows(table, filters, limit=2):
            return unwrap_data_value(self._gateway.query(table, "*", filters=filters, limit=limit))

        def one(table, key, value):
            found = rows(table, (DataFilter.eq(key, value),))
            if len(found) != 1 or found[0].get(key) != value:
                raise ValueError(f"unique explicit {table} linkage required")
            return found[0]

        def equal(left, right, key, *, required=True):
            if required and (not left.get(key) or not right.get(key)):
                raise ValueError(f"missing canonical {key}")
            if left.get(key) is not None and left.get(key) != right.get(key):
                raise ValueError(f"canonical {key} mismatch")

        def observed(row):
            if (row.get("synthetic") is True or row.get("forecast_derived") is True
                    or row.get("verified") is False):
                raise ValueError("unverified canonical outreach linkage")
            for key in ("created_at", "opened_at", "updated_at", "received_at"):
                if row.get(key):
                    clock = datetime.fromisoformat(str(row[key]).replace("Z", "+00:00"))
                    if clock.tzinfo is None or clock > as_of:
                        raise ValueError("future canonical outreach linkage")

        intent = one("outbound_intents", "id", intent_id)
        observed(intent)
        for key in ("prospect_id", "buyer_id", "opportunity_id"):
            equal(raw, intent, key, required=False)
        metadata = intent.get("metadata") or {}
        if (raw.get("metadata") or {}).get("adaptive_outreach") != metadata.get("adaptive_outreach"):
            raise ValueError("outreach experiment metadata mismatch")
        case = one("closer_cases", "outbound_intent_id", intent_id)
        observed(case)
        if not case.get("reply_id") or (require_order and not case.get("fulfilment_order_id")):
            raise ValueError("missing explicit reply/order linkage")
        reply = one("outbound_replies", "id", case["reply_id"])
        observed(reply)
        if reply.get("intent_id") != intent_id:
            raise ValueError("canonical reply outbound intent mismatch")
        order = one("fulfilment_orders", "id", case["fulfilment_order_id"]) if case.get("fulfilment_order_id") else None
        if order:
            observed(order)
        for key in ("prospect_id", "buyer_id", "opportunity_id"):
            if order:
                equal(case, order, key)
            equal(intent, case, key, required=key == "prospect_id")
        for row in (raw, metadata):
            equal(row, {"fulfilment_order_id": (order or {}).get("id")}, "fulfilment_order_id", required=False)
        for key in ("prospect_id", "buyer_id", "opportunity_id"):
            equal(metadata, case, key, required=False)
        if metadata.get("outbound_intent_id") not in (None, intent_id):
            raise ValueError("intent metadata outbound intent mismatch")
        one("prospects", "id", case["prospect_id"])
        one("gtm_opportunities", "id", case["opportunity_id"])
        buyer = one("buyers", "id", case["buyer_id"])
        tenant_id = buyer.get("org_id")
        if not tenant_id:
            raise ValueError("canonical buyer tenant missing")
        for row in (raw, intent, metadata, case, order or {}, reply):
            if row.get("tenant_id") is not None and row["tenant_id"] != tenant_id:
                raise ValueError("outreach tenant mismatch")

        conversations = rows("empire_conversations", (DataFilter.eq("outbound_intent_id", intent_id),))
        if len(conversations) > 1:
            raise ValueError("ambiguous canonical outreach conversation")
        for conversation in conversations:
            observed(conversation)
            if conversation.get("outbound_intent_id") != intent_id:
                raise ValueError("conversation outbound intent mismatch")
            for key in ("prospect_id", "buyer_id", "opportunity_id"):
                equal(conversation, case, key, required=False)
            if conversation.get("closer_case_id") not in (None, case["id"]):
                raise ValueError("conversation closer case mismatch")
            if conversation.get("tenant_id") not in (None, tenant_id):
                raise ValueError("conversation tenant mismatch")

        canonical_identity = dict(reply_id=reply["id"], closer_case_id=case["id"],
            conversation_id=conversations[0]["id"] if conversations else None)
        for row in (raw, metadata):
            for key, value in canonical_identity.items():
                if row.get(key) is not None and row[key] != value:
                    raise ValueError(f"canonical outreach {key} mismatch")
        claimed = (order or {}).get("commercial_payload", {}).get("causal_lineage") or metadata.get("causal_lineage")
        causal = None
        if require_order or claimed is not None:
            causal = validate_causal_lineage(claimed)
            if causal["tenant_id"] != tenant_id or causal["opportunity_id"] != case["opportunity_id"]:
                raise ValueError("outreach causal scope mismatch")
            if require_order and causal["causal_eligible"] is not True:
                raise ValueError("outreach causal execution unavailable")
            if (metadata.get("causal_lineage") != causal
                    or metadata.get("department_work_id") != causal["task_key"]
                    or metadata.get("opportunity_key") != causal["opportunity_key"]
                    or order and (order.get("commercial_payload") or {}).get("causal_lineage") != causal):
                raise ValueError("outbound intent causal execution mismatch or missing")
            for key in ("prediction_ref", "decision_ref", "execution_ref"):
                for row in (raw, metadata):
                    if key in row and row[key] != causal[key]:
                        raise ValueError(f"outreach {key} mismatch")
            if not require_order:
                from empire_os.department_work_queue import DepartmentWorkQueue
                from empire_os.decision_identity import causal_lineage_from_work
                work = DepartmentWorkQueue.read_completed_work(repo_root, causal["task_key"])
                if causal_lineage_from_work(work, tenant_id=tenant_id, opportunity_key=causal["opportunity_key"],
                        opportunity_id=case["opportunity_id"], claimed_lineage=causal) != causal:
                    raise ValueError("middle funnel canonical work mismatch")
                if datetime.fromisoformat(work["updated_at"].replace("Z", "+00:00")) > as_of:
                    raise ValueError("future middle funnel execution evidence")
        if causal is None:
            for row in (raw, metadata):
                if any(row.get(key) is not None for key in ("prediction_ref", "decision_ref", "execution_ref")):
                    raise ValueError("outreach lineage references lack canonical provenance")
        return dict(raw=raw, intent=intent, case=case, reply=reply, order=order,
                    conversations=conversations, tenant_id=tenant_id, causal=causal)

    def outreach_verified_outcome_record(self, record: Mapping[str, Any], *, repo_root,
                                         as_of: datetime) -> dict[str, Any]:
        """Existing V2C verified outcome bridge, using shared canonical identity checks."""
        from empire_os.outcome_feedback import validate_verified_feedback
        linked = self._outreach_canonical_linkage(record, repo_root=repo_root, as_of=as_of)
        raw, case, reply, order = (linked[key] for key in ("raw", "case", "reply", "order"))
        conversations, tenant_id, causal = (linked[key] for key in ("conversations", "tenant_id", "causal"))
        intent_id = raw["intent_id"]
        feedback = self.verified_outcome_feedback(order["id"], tenant_id=tenant_id,
            repo_root=repo_root, as_of=as_of)
        validate_verified_feedback(feedback, tenant_id=tenant_id, as_of=as_of)
        if feedback.get("causal_lineage") != causal:
            raise ValueError("verified outcome causal execution mismatch")
        expected = dict(tenant_id=tenant_id, prospect_id=case["prospect_id"], buyer_id=case["buyer_id"],
                        fulfilment_order_id=order["id"])
        for key in expected:
            if not expected[key] or expected[key] != feedback.get(key):
                raise ValueError(f"canonical feedback {key} mismatch")
        for row in (raw, linked["intent"].get("metadata") or {}):
            if row.get("outcome_ref") is not None and row["outcome_ref"] != feedback.get("outcome_ref"):
                raise ValueError("outreach outcome mismatch")
        attribution = dict(schema_version="empire.outreach-outcome-attribution.v1",
            outbound_intent_id=intent_id, closer_case_id=case["id"], reply_id=reply["id"],
            conversation_id=conversations[0]["id"] if conversations else None,
            **expected, opportunity_id=case["opportunity_id"], outcome_ref=feedback["outcome_ref"],
            prediction_ref=feedback.get("prediction_ref"), decision_ref=feedback.get("decision_ref"),
            execution_ref=feedback.get("execution_ref"), causal_lineage=causal,
            execution_authority="none")
        return {**raw, **expected, "outbound_intent_id": intent_id,
                "opportunity_id": case["opportunity_id"], "outcome_ref": feedback["outcome_ref"],
                "prediction_ref": feedback.get("prediction_ref"), "decision_ref": feedback.get("decision_ref"),
                "execution_ref": feedback.get("execution_ref"), "verified_outcome_feedback": feedback,
                "outreach_outcome_attribution": attribution, "outcome_bridge_state": "VERIFIED"}

    def outreach_middle_funnel_record(self, record: Mapping[str, Any], *, repo_root,
                                      as_of: datetime) -> dict[str, Any]:
        """Independent middle-stage observations from existing closer/terms persistence."""
        from empire_os.conversation_qualification import build_persisted_qualification_stage, _observed_stage_row, _stage_time
        from empire_os.commercial_terms_materializer import build_persisted_terms_stage
        linked = self._outreach_canonical_linkage(record, repo_root=repo_root, as_of=as_of, require_order=False)
        raw, case, reply, order = (linked[key] for key in ("raw", "case", "reply", "order"))
        conversations, causal = linked["conversations"], linked["causal"]
        context = dict(tenant_id=linked["tenant_id"], outbound_intent_id=raw["intent_id"], closer_state=case.get("state"),
            reply_id=reply["id"], closer_case_id=case["id"], prospect_id=case["prospect_id"],
            buyer_id=case["buyer_id"], opportunity_id=case["opportunity_id"],
            conversation_id=conversations[0]["id"] if conversations else None,
            fulfilment_order_id=(order or {}).get("id"),
            prediction_ref=(causal or {}).get("prediction_ref"), decision_ref=(causal or {}).get("decision_ref"),
            execution_ref=(causal or {}).get("execution_ref"), outcome_ref=None,
            execution_authority="none")
        result = {**raw, **context, "qualified_conversation_state": "UNKNOWN", "commercial_terms_state": "UNKNOWN"}
        events = unwrap_data_value(self._gateway.query("closer_events", "*",
            filters=(DataFilter.eq("case_id", case["id"]), DataFilter.eq("event_type", "state_advanced")), limit=100))
        if len(events) >= 100:
            raise ValueError("incomplete qualification history")
        qualified = {e.get("id"): e for e in events if (e.get("payload") or {}).get("state") == "qualified"}
        if len(qualified) == 1:
            try:
                event = next(iter(qualified.values()))
                if datetime.fromisoformat(str(reply["received_at"]).replace("Z", "+00:00")) > datetime.fromisoformat(str(event["occurred_at"]).replace("Z", "+00:00")):
                    raise ValueError("qualification predates canonical reply")
                stage = build_persisted_qualification_stage(event, context=context, as_of=as_of)
            except (ValueError, TypeError, KeyError):
                pass
            else:
                result["qualified_conversation_evidence"] = stage
                result["qualified_conversation_state"] = stage["state"]
        if order:
            payload = order.get("commercial_payload") or {}
            review_id = payload.get("commercial_terms_review_id")
            reviews = unwrap_data_value(self._gateway.query("commercial_terms_reviews", "*",
                filters=(DataFilter.eq("id", review_id),) if review_id else (DataFilter.eq("fulfilment_order_id", order["id"]),),
                order=(OrderSpec("proposed_at", descending=True), OrderSpec("id", descending=True)), limit=2))
            if len(reviews) == 1:
                review = reviews[0]
                try:
                    _observed_stage_row(review, as_of=as_of)
                    if review.get("fulfilment_order_id") != order["id"] or (review_id and review.get("id") != review_id):
                        raise ValueError("terms diagnostic identity mismatch")
                    result["commercial_terms_state"] = {"pending": "PROPOSED", "approved": "UNKNOWN", "rejected": "REJECTED", "expired": "EXPIRED"}.get(review.get("status"), "UNKNOWN")
                    for source in (review, review.get("terms") or {}, payload):
                        if source.get("expires_at") and _stage_time(source["expires_at"]) <= as_of:
                            result["commercial_terms_state"] = "EXPIRED"
                except (ValueError, TypeError, KeyError):
                    pass
                terms_events = unwrap_data_value(self._gateway.query("commercial_terms_events", "*",
                    filters=(DataFilter.eq("review_id", review.get("id")),), limit=100))
                try:
                    if len(terms_events) >= 100:
                        raise ValueError("incomplete commercial terms history")
                    stage = build_persisted_terms_stage(order, review, terms_events, context=context, as_of=as_of)
                except (ValueError, TypeError, KeyError):
                    pass
                else:
                    result["commercial_terms_evidence"] = stage
                    result["commercial_terms_state"] = stage["state"]
        return result

    def outreach_performance_records(self, *, lookback_days: int, repo_root,
                                    as_of: datetime) -> list[dict[str, Any]]:
        """Existing derived snapshot intake, with bounded fail-closed enrichment."""
        from empire_os.department_work_queue import DepartmentWorkQueueError
        if self._gateway.snapshot().as_dict().get("primary_backend") != "empiredb":
            raise ValueError("canonical EmpireDB required for outreach snapshot")
        if as_of.tzinfo is None:
            raise ValueError("timezone-aware outreach snapshot required")
        days = max(1, min(int(lookback_days), 365))
        intents = unwrap_data_value(self._gateway.query("outbound_intents",
            "id,prospect_id,buyer_id,opportunity_id,offer_key,status,metadata,created_at,updated_at",
            filters=(DataFilter.gte("created_at", as_of - timedelta(days=days)),),
            order=(OrderSpec("created_at"), OrderSpec("id")), limit=10000))
        if len(intents) >= 10000:
            raise ValueError("outreach snapshot intake limit reached; incomplete learning forbidden")
        records = []
        for intent in intents:
            replies = unwrap_data_value(self._gateway.query("outbound_replies", "id,intent_id,classification",
                filters=(DataFilter.eq("intent_id", intent["id"]),),
                order=(OrderSpec("received_at", descending=True), OrderSpec("id", descending=True)), limit=1))
            record = {**intent, "intent_id": intent["id"], "outbound_intent_id": intent["id"],
                      "delivered": intent.get("status") in ("delivered", "replied") or bool(replies),
                      "classification": replies[0].get("classification") if replies else None}
            if not isinstance((intent.get("metadata") or {}).get("adaptive_outreach"), Mapping):
                record["outcome_bridge_state"] = "UNLABELLED"
                records.append(record)
                continue
            middle = {"qualified_conversation_state": "UNKNOWN", "commercial_terms_state": "UNKNOWN"}
            try:
                middle = self.outreach_middle_funnel_record(record, repo_root=repo_root, as_of=as_of)
            except (ValueError, TypeError, KeyError, FileNotFoundError, DepartmentWorkQueueError):
                pass
            try:
                enriched = self.outreach_verified_outcome_record(record, repo_root=repo_root, as_of=as_of)
            except (ValueError, TypeError, KeyError, FileNotFoundError, DepartmentWorkQueueError) as exc:
                # Do not expose data/SQL/secrets from exception messages.
                record["outcome_bridge_state"] = "UNKNOWN"
                record["outcome_bridge_reason"] = type(exc).__name__
                enriched = record
            enriched = ({**middle, **enriched} if enriched.get("outcome_bridge_state") == "VERIFIED"
                        else {**enriched, **middle})
            for stage in ("qualified_conversation", "commercial_terms"):
                if middle.get(stage + "_evidence"):
                    evidence = dict(middle[stage + "_evidence"])
                    evidence["outcome_ref"] = enriched.get("outcome_ref")
                    enriched[stage + "_evidence"] = evidence
            records.append(enriched)
        return records

    def snapshot(self) -> dict[str, object]:
        backend = self._gateway.snapshot().as_dict()
        return {
            "backend": backend["primary_backend"],
            "configured": backend["configured"],
            "dual_write_enabled": backend["dual_write_enabled"],
            "write_fallback_enabled": backend["write_fallback_enabled"],
            "repository_authority": "execution_bus_bounded",
        }
