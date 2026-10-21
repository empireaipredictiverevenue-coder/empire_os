"""Restricted Postgres transactional consumer-opt-in repository.

NOT connected to production. No DSN/environment lookup, no public roles,
and no migration execution. Requires operator-injected, privately scoped
psycopg connection factory plus approved RLS policies before use.

Every state transition is one transaction, serialized per HMAC lookup.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime, timezone
from typing import Any

from empire_os.consumer_optin_token_security import review_token_use

PURPOSE = "empire_own_brand_homeowner_updates"
NOTICE = "roofing-homeowner-updates-v1"
DIGEST = re.compile(r"^[a-f0-9]{64}$")


class ConsumerPostgresRepository:
    def __init__(self, *, connection_factory: Callable[[], AbstractContextManager],
                 approved_custody: bool = False):
        if not callable(connection_factory):
            raise ValueError("injected private PostgreSQL connector required")
        self._connect = connection_factory
        self._approved = approved_custody

    def signup_writable(self) -> bool:
        # Enabling a Python constructor alone is not sufficient: deployment
        # must also provision an isolated, narrowly RLS-authorized DB role.
        return self._approved

    def token_processing_writable(self) -> bool:
        return self._approved

    @staticmethod
    def _digest(value: str) -> None:
        if not isinstance(value, str) or DIGEST.fullmatch(value) is None:
            raise ValueError("invalid keyed digest")

    def begin_pending(
        self, *, lookup: str, ciphertext: bytes, key_ref: str,
        capture_digest: str, confirm_hmac: str, confirm_expires: datetime,
        unsubscribe_hmac: str, unsubscribe_expires: datetime,
    ) -> bool:
        if not self.signup_writable():
            return False
        for v in (lookup, capture_digest, confirm_hmac, unsubscribe_hmac):
            self._digest(v)
        if (not isinstance(ciphertext, bytes) or not 34 <= len(ciphertext) <= 2048
            or not isinstance(key_ref, str) or not key_ref.startswith("consumer-key-v")
            or confirm_hmac == unsubscribe_hmac
            or any(t.tzinfo is None for t in (confirm_expires, unsubscribe_expires))):
            raise ValueError("invalid original consent encryption or token custody")
        with self._connect() as conn:
            # Advisory lock serializes signup with a concurrent unsubscribe.
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (lookup,))
            suppressed = conn.execute(
                "SELECT 1 FROM public.empire_consumer_email_suppressions "
                "WHERE email_lookup_hmac=%s AND purpose=%s",
                (lookup, PURPOSE),
            ).fetchone()
            if suppressed:
                return False
            old = conn.execute(
                "SELECT subscription_id, permission_state "
                "FROM public.empire_consumer_subscriptions "
                "WHERE email_lookup_hmac=%s AND purpose=%s FOR UPDATE",
                (lookup, PURPOSE),
            ).fetchone()
            if old:
                subscription_id, state = old
                if state != "pending_verification":
                    return False
                conn.execute(
                    "UPDATE public.empire_consumer_subscriptions "
                    "SET email_ciphertext=%s,email_key_reference=%s,"
                    "consent_capture_digest=%s "
                    "WHERE subscription_id=%s AND permission_state='pending_verification'",
                    (ciphertext, key_ref, capture_digest, subscription_id),
                )
                # Older pending links cannot override the newest request.
                conn.execute(
                    "UPDATE public.empire_consumer_one_time_tokens "
                    "SET consumed_at=clock_timestamp() "
                    "WHERE subscription_id=%s AND consumed_at IS NULL",
                    (subscription_id,),
                )
            else:
                inserted = conn.execute(
                    "INSERT INTO public.empire_consumer_subscriptions "
                    "(email_lookup_hmac,email_ciphertext,email_key_reference,"
                    "consent_notice_version,consent_capture_digest,source_evidence_kind) "
                    "VALUES (%s,%s,%s,%s,%s,'ORIGINAL_FIRST_PARTY_OPTIN_RECEIPT') "
                    "RETURNING subscription_id",
                    (lookup, ciphertext, key_ref, NOTICE, capture_digest),
                ).fetchone()
                if not inserted:
                    raise RuntimeError("original subscription insert not attested")
                subscription_id = inserted[0]

            conn.execute(
                "INSERT INTO public.empire_consumer_consent_events "
                "(subscription_id,consent_action,notice_version,evidence_digest,evidence_method) "
                "VALUES (%s,'opt_in_requested',%s,%s,'ORIGINAL_BROWSER_CHOICE')",
                (subscription_id, NOTICE, capture_digest),
            )
            for fingerprint, kind, expiry in (
                (confirm_hmac, "confirm", confirm_expires),
                (unsubscribe_hmac, "unsubscribe", unsubscribe_expires),
            ):
                conn.execute(
                    "INSERT INTO public.empire_consumer_one_time_tokens "
                    "(token_hmac,subscription_id,token_purpose,expires_at) "
                    "VALUES (%s,%s,%s,%s)",
                    (fingerprint, subscription_id, kind, expiry),
                )
            # psycopg connection context commits only when every step succeeds.
        return True

    def claim_confirmation_send(self, *, lookup: str, confirm_hmac: str) -> bool:
        """Single-use, private provider-send claim with fresh suppression."""
        if not self.signup_writable():
            return False
        self._digest(lookup)
        self._digest(confirm_hmac)
        with self._connect() as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (lookup,)
            )
            if conn.execute(
                "SELECT 1 FROM public.empire_consumer_email_suppressions "
                "WHERE email_lookup_hmac=%s AND purpose=%s",
                (lookup, PURPOSE),
            ).fetchone():
                return False
            record = conn.execute(
                "SELECT s.subscription_id FROM public.empire_consumer_subscriptions s "
                "JOIN public.empire_consumer_one_time_tokens t "
                "ON s.subscription_id=t.subscription_id "
                "WHERE s.email_lookup_hmac=%s AND s.permission_state='pending_verification' "
                "AND t.token_hmac=%s AND t.token_purpose='confirm' "
                "AND t.send_claimed_at IS NULL AND t.consumed_at IS NULL "
                "AND t.expires_at>clock_timestamp() FOR UPDATE OF s,t",
                (lookup, confirm_hmac),
            ).fetchone()
            if not record:
                return False
            changed=conn.execute(
                "UPDATE public.empire_consumer_one_time_tokens "
                "SET send_claimed_at=clock_timestamp() "
                "WHERE token_hmac=%s AND send_claimed_at IS NULL "
                "RETURNING token_hmac", (confirm_hmac,),
            ).fetchone()
            return changed is not None

    def record_confirmation_delivery(
        self, *, lookup: str, confirm_hmac: str, provider_receipt: str,
    ) -> bool:
        if not self.signup_writable():
            return False
        for val in (lookup, confirm_hmac, provider_receipt):
            self._digest(val)
        with self._connect() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",(lookup,))
            row = conn.execute(
                "SELECT s.subscription_id FROM public.empire_consumer_subscriptions s "
                "JOIN public.empire_consumer_one_time_tokens t "
                "ON t.subscription_id=s.subscription_id "
                "WHERE s.email_lookup_hmac=%s AND s.permission_state='pending_verification' "
                "AND t.token_hmac=%s AND t.token_purpose='confirm' "
                "AND t.consumed_at IS NULL AND t.send_claimed_at IS NOT NULL "
                "AND t.expires_at>clock_timestamp() "
                "FOR UPDATE OF s,t",
                (lookup, confirm_hmac),
            ).fetchone()
            if not row:
                return False
            conn.execute(
                "INSERT INTO public.empire_consumer_delivery_receipts "
                "(token_hmac,subscription_id,provider_receipt_hmac) "
                "VALUES (%s,%s,%s) ON CONFLICT (token_hmac) DO NOTHING",
                (confirm_hmac, row[0], provider_receipt),
            )
        return True

    def consume_once(self, *, token_hmac: str, action: str,
                     checked_at: datetime) -> bool:
        if not self.token_processing_writable():
            return False
        self._digest(token_hmac)
        if action not in ("confirm", "unsubscribe"):
            return False
        if checked_at.tzinfo is None:
            raise ValueError("UTC-aware clock required")
        with self._connect() as conn:
            # Lock token first, then serialise all operations on its contact.
            row = conn.execute(
                "SELECT t.subscription_id,s.email_lookup_hmac "
                "FROM public.empire_consumer_one_time_tokens t "
                "JOIN public.empire_consumer_subscriptions s "
                "ON s.subscription_id=t.subscription_id "
                "WHERE t.token_hmac=%s AND t.token_purpose=%s",
                (token_hmac, action),
            ).fetchone()
            if not row:
                return False
            subscription_id, lookup = row
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",(lookup,))
            locked = conn.execute(
                "SELECT t.expires_at,t.consumed_at,s.permission_state "
                "FROM public.empire_consumer_one_time_tokens t "
                "JOIN public.empire_consumer_subscriptions s "
                "ON s.subscription_id=t.subscription_id "
                "WHERE t.token_hmac=%s AND t.token_purpose=%s "
                "FOR UPDATE OF s,t",
                (token_hmac, action),
            ).fetchone()
            if not locked:
                return False
            expires_at, consumed_at, state = locked
            if consumed_at is not None or checked_at >= expires_at:
                return False
            if conn.execute(
                "SELECT 1 FROM public.empire_consumer_email_suppressions "
                "WHERE email_lookup_hmac=%s AND purpose=%s", (lookup,PURPOSE)
            ).fetchone():
                return False
            if action == "confirm":
                if state != "pending_verification":
                    return False
                delivered=conn.execute(
                    "SELECT 1 FROM public.empire_consumer_delivery_receipts "
                    "WHERE token_hmac=%s AND subscription_id=%s",
                    (token_hmac,subscription_id),
                ).fetchone()
                if not delivered:
                    return False
                conn.execute(
                    "UPDATE public.empire_consumer_subscriptions SET "
                    "permission_state='verified',verified_at=%s "
                    "WHERE subscription_id=%s",
                    (checked_at,subscription_id),
                )
                receipt_action,method = "opt_in_verified","VERIFIED_EMAIL_TOKEN"
            else:
                if state not in ("pending_verification","verified"):
                    return False
                conn.execute(
                    "INSERT INTO public.empire_consumer_email_suppressions "
                    "(email_lookup_hmac,purpose,reason) "
                    "VALUES (%s,%s,'unsubscribe') "
                    "ON CONFLICT (email_lookup_hmac) DO NOTHING",
                    (lookup,PURPOSE),
                )
                conn.execute(
                    "UPDATE public.empire_consumer_subscriptions SET "
                    "permission_state='unsubscribed',revoked_at=%s "
                    "WHERE subscription_id=%s",
                    (checked_at,subscription_id),
                )
                # All confirmation and unsubscribe tokens are now unusable.
                conn.execute(
                    "UPDATE public.empire_consumer_one_time_tokens SET consumed_at=%s "
                    "WHERE subscription_id=%s AND consumed_at IS NULL",
                    (checked_at,subscription_id),
                )
                receipt_action,method = "unsubscribed","AUTHENTICATED_WITHDRAWAL"
            conn.execute(
                "UPDATE public.empire_consumer_one_time_tokens SET consumed_at=%s "
                "WHERE token_hmac=%s AND consumed_at IS NULL",
                (checked_at,token_hmac),
            )
            conn.execute(
                "INSERT INTO public.empire_consumer_consent_events "
                "(subscription_id,consent_action,notice_version,evidence_digest,evidence_method) "
                "VALUES (%s,%s,%s,%s,%s)",
                (subscription_id,receipt_action,NOTICE,token_hmac,method),
            )
        return True

    def apply_verified_privacy_action(
        self, *, lookup: str, action: str, evidence_hmac: str,
        checked_at: datetime,
    ) -> bool:
        """Handle verified bounce/complaint or owner-authorised erasure atomically.

        Entry points MUST authenticate the email-provider webhook signature or
        the original privacy-owner's request before calling this method. This
        interface accepts only a keyed contact digest, never email plaintext.
        The caller supplies independent evidence; this method does not validate
        webhook signatures or authorise a privacy deletion by itself.
        """
        if not self.token_processing_writable():
            return False
        self._digest(lookup)
        self._digest(evidence_hmac)
        if action not in ("bounce", "complaint", "privacy_erasure"):
            return False
        if checked_at.tzinfo is None or checked_at.utcoffset() is None:
            raise ValueError("UTC-aware verified action timestamp required")

        with self._connect() as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (lookup,)
            )
            row = conn.execute(
                "SELECT subscription_id, permission_state "
                "FROM public.empire_consumer_subscriptions "
                "WHERE email_lookup_hmac=%s AND purpose=%s FOR UPDATE",
                (lookup, PURPOSE),
            ).fetchone()
            if row and row[1] == "erased":
                return False
            if row and row[1] == "unsubscribed" and action != "privacy_erasure":
                return False

            # A suppression record prevents a later consent import even if
            # there is currently no corresponding subscriber row.
            reason = "privacy_request" if action == "privacy_erasure" else action
            conn.execute(
                "INSERT INTO public.empire_consumer_email_suppressions "
                "(email_lookup_hmac,purpose,reason) VALUES (%s,%s,%s) "
                "ON CONFLICT (email_lookup_hmac) DO NOTHING",
                (lookup, PURPOSE, reason),
            )
            if not row:
                return True

            subscription_id, _ = row
            if action == "privacy_erasure":
                # Never delete immutable legal/custody records without a
                # separate approved retention policy, but remove the encrypted
                # address and its decryption-key reference in this transaction.
                conn.execute(
                    "UPDATE public.empire_consumer_subscriptions SET "
                    "permission_state='erased',email_ciphertext=NULL,"
                    "email_key_reference=NULL,revoked_at=%s,erased_at=%s "
                    "WHERE subscription_id=%s",
                    (checked_at, checked_at, subscription_id),
                )
                consent_actions = ("erasure_requested", "erasure_completed")
                method = "PRIVACY_OWNER_ERASURE"
            else:
                conn.execute(
                    "UPDATE public.empire_consumer_subscriptions SET "
                    "permission_state='unsubscribed',revoked_at=%s "
                    "WHERE subscription_id=%s",
                    (checked_at, subscription_id),
                )
                consent_actions = ("suppressed_" + action,)
                method = "VERIFIED_PROVIDER_EVENT"

            conn.execute(
                "UPDATE public.empire_consumer_one_time_tokens "
                "SET consumed_at=clock_timestamp() "
                "WHERE subscription_id=%s AND consumed_at IS NULL",
                (subscription_id,),
            )
            for consent_action in consent_actions:
                conn.execute(
                    "INSERT INTO public.empire_consumer_consent_events "
                    "(subscription_id,consent_action,notice_version,evidence_digest,evidence_method) "
                    "VALUES (%s,%s,%s,%s,%s)",
                    (subscription_id, consent_action, NOTICE,
                     evidence_hmac, method),
                )
        return True
