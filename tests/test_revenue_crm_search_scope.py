from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from empire_os.revenue_crm_search_scope import (
    AccountSiteBinding, SearchScopeUnavailable, resolve_search_scope,
)

T, P, E, S, OTHER = [f"00000000-0000-0000-0000-{n:012d}" for n in range(1, 6)]
NOW = datetime(2026, 10, 25, tzinfo=timezone.utc)


class SearchScopeTests(unittest.TestCase):
    def setUp(self):
        self.row = AccountSiteBinding(
            T, P, E, S, "legacy-search-key", "fixture:approved-binding",
            NOW - timedelta(days=1), NOW + timedelta(days=1),
        )

    def resolve(self, rows, **kwargs):
        args = dict(authenticated_tenant_id=T, prospect_id=P, site_id=S,
                    authorized_entity_id=E, server_bindings=rows, now=NOW)
        args.update(kwargs)
        return resolve_search_scope(**args)

    def test_server_mapping_keeps_search_key_distinct_from_tenant_uuid(self):
        scope = self.resolve((self.row,))
        self.assertEqual(scope.tenant_id, T)
        self.assertEqual(scope.tenant_key, "legacy-search-key")
        self.assertEqual(scope.binding_evidence_ref, "fixture:approved-binding")

    def test_each_identity_boundary_rejects_foreign_rows(self):
        for field in ("tenant_id", "prospect_id", "entity_id", "site_id"):
            with self.subTest(field=field), self.assertRaises(SearchScopeUnavailable):
                self.resolve((replace(self.row, **{field: OTHER}),))

    def test_missing_or_duplicate_current_binding_is_unavailable(self):
        for rows in ((), (self.row, self.row)):
            with self.assertRaises(SearchScopeUnavailable):
                self.resolve(rows)

    def test_revoked_future_and_expired_bindings_are_unavailable(self):
        for changes in (dict(active=False), dict(valid_from=NOW + timedelta(hours=1)),
                        dict(valid_until=NOW)):
            with self.subTest(changes=changes), self.assertRaises(SearchScopeUnavailable):
                self.resolve((replace(self.row, **changes),))

    def test_historical_record_does_not_duplicate_current_binding(self):
        expired = replace(self.row, valid_until=NOW)
        self.assertEqual(self.resolve((expired, self.row)).site_id, S)

    def test_malformed_provenance_key_or_state_fails_closed(self):
        for changes in (dict(evidence_ref=""), dict(evidence_ref="  "),
                        dict(tenant_key=" x "), dict(active=1)):
            with self.subTest(changes=changes), self.assertRaises(SearchScopeUnavailable):
                self.resolve((replace(self.row, **changes),))

    def test_naive_and_invalid_validity_times_fail_closed(self):
        for changes in (dict(valid_from=NOW.replace(tzinfo=None)),
                        dict(valid_until=self.row.valid_from)):
            with self.assertRaises(SearchScopeUnavailable):
                self.resolve((replace(self.row, **changes),))
        with self.assertRaises(SearchScopeUnavailable):
            self.resolve((self.row,), now=NOW.replace(tzinfo=None))

    def test_malformed_request_identity_is_rejected(self):
        with self.assertRaises(SearchScopeUnavailable):
            self.resolve((self.row,), prospect_id="not-a-uuid")


if __name__ == "__main__":
    unittest.main()
