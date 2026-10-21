"""Purpose-limited real PostgreSQL suppression guard for confirmation sends.

This is an *additional* check at the transactional sender boundary, not a
replacement for the repository's claim lock. It makes no changes and exposes
only a boolean. Must use the dedicated consumer role connection factory.
No default credentials, public route, SMTP key or service activation.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from empire_os.consumer_optin_token_security import (
    canonical_email, email_lookup_hmac
)


@dataclass
class ConsumerPrivateSuppressionReader:
    connect: Callable
    lookup_key: bytes
    approved_private_custody: bool = False

    def __post_init__(self) -> None:
        if not callable(self.connect):
            raise ValueError("PRIVATE_CONNECTION_FACTORY_REQUIRED")
        if not isinstance(self.lookup_key, bytes) or len(self.lookup_key)!=32:
            raise ValueError("PURPOSE_SEPARATED_256_BIT_LOOKUP_REQUIRED")

    def __call__(self, email: str) -> bool:
        if self.approved_private_custody is not True:
            return False
        lookup=email_lookup_hmac(canonical_email(email),key=self.lookup_key)
        try:
            with self.connect() as conn:
                # The verification must have been claimed once, be pending,
                # and have a current unexpired token. Suppression overrides.
                row=conn.execute(
                    "SELECT EXISTS("
                    " SELECT 1 FROM public.empire_consumer_subscriptions s"
                    " JOIN public.empire_consumer_one_time_tokens t"
                    " ON t.subscription_id=s.subscription_id"
                    " WHERE s.email_lookup_hmac=%s"
                    " AND s.tenant_scope='empire-ai.co.uk'"
                    " AND s.purpose='empire_own_brand_homeowner_updates'"
                    " AND s.permission_state='pending_verification'"
                    " AND t.token_purpose='confirm'"
                    " AND t.send_claimed_at IS NOT NULL"
                    " AND t.consumed_at IS NULL"
                    " AND t.expires_at>clock_timestamp()"
                    " AND NOT EXISTS("
                    " SELECT 1 FROM public.empire_consumer_email_suppressions x"
                    " WHERE x.email_lookup_hmac=s.email_lookup_hmac"
                    " AND x.purpose='empire_own_brand_homeowner_updates'"
                    " )"
                    ")",
                    (lookup,)
                ).fetchone()
                return bool(row and row[0] is True)
        except Exception:
            # Fail closed rather than transmitting to anyone after an
            # unknown suppression status or a private DB outage.
            return False
